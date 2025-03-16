import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time

class CurrencyConverter:
    """
    A class to handle currency conversion operations using ExchangeRate-API
    with advanced features including caching and historical data.
    """
    
    def __init__(self):
        """Initialize the CurrencyConverter with caching functionality."""
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".currency_cache")
        self.cache_file = os.path.join(self.cache_dir, "exchange_rates.json")
        self.historical_dir = os.path.join(self.cache_dir, "historical")
        self.cache_timeout = 3600  # Cache timeout in seconds (1 hour)
        self.currencies = []
        self.available_currencies = {}
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        if not os.path.exists(self.historical_dir):
            os.makedirs(self.historical_dir)
            
        # Initialize currencies list
        self.load_currencies()
    
    def load_currencies(self):
        """Load available currencies and their names."""
        try:
            # First check if we have cached currency list
            if os.path.exists(os.path.join(self.cache_dir, "currencies.json")):
                with open(os.path.join(self.cache_dir, "currencies.json"), "r") as f:
                    data = json.load(f)
                    if datetime.now().timestamp() - data.get("timestamp", 0) < 86400:  # 24 hours
                        self.available_currencies = data.get("currencies", {})
                        self.currencies = sorted(list(self.available_currencies.keys()))
                        return
            
            # If no cache or expired, fetch from API
            response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
            response.raise_for_status()
            rates = response.json().get("rates", {})
            
            # Create a dictionary of currencies with names (using codes as names for now)
            self.available_currencies = {code: code for code in rates.keys()}
            self.currencies = sorted(list(self.available_currencies.keys()))
            
            # Cache the currencies
            with open(os.path.join(self.cache_dir, "currencies.json"), "w") as f:
                json.dump({
                    "timestamp": datetime.now().timestamp(),
                    "currencies": self.available_currencies
                }, f)
                
        except Exception as e:
            # If fetching fails, use a default list of common currencies
            self.currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR"]
            self.available_currencies = {code: code for code in self.currencies}
            print(f"Error loading currencies: {e}")
    
    def get_exchange_rate(self, base_currency):
        """
        Get exchange rates for a base currency, using cache if available and not expired.
        
        Args:
            base_currency (str): Base currency code (e.g., 'USD')
            
        Returns:
            dict: Dictionary of exchange rates
        """
        # Check if we have a valid cached file
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                try:
                    cache_data = json.load(f)
                    if (base_currency in cache_data and 
                        (time.time() - cache_data[base_currency]["timestamp"]) < self.cache_timeout):
                        return cache_data[base_currency]["rates"]
                except (json.JSONDecodeError, KeyError):
                    # Cache file is corrupted or missing expected structure
                    pass
        
        # No valid cache, fetch from API
        try:
            url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            self._cache_rates(base_currency, data["rates"])
            
            # Store for historical tracking
            self._store_historical(base_currency, data["rates"])
            
            return data["rates"]
        except Exception as e:
            raise Exception(f"Error fetching exchange rates: {e}")
    
    def _cache_rates(self, base_currency, rates):
        """Cache the exchange rates for a base currency."""
        # Initialize cache dictionary if file doesn't exist
        cache_data = {}
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)
            except json.JSONDecodeError:
                # File is corrupted, start with empty cache
                pass
        
        # Update cache with new data
        cache_data[base_currency] = {
            "timestamp": time.time(),
            "rates": rates
        }
        
        # Write back to cache file
        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f)
    
    def _store_historical(self, base_currency, rates):
        """Store historical rates for trend analysis."""
        today = datetime.now().strftime("%Y-%m-%d")
        hist_file = os.path.join(self.historical_dir, f"{base_currency}_{today}.json")
        
        # Don't duplicate entries for same day
        if os.path.exists(hist_file):
            return
            
        with open(hist_file, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "rates": rates
            }, f)
    
    def convert_currency(self, base_currency, target_currency, amount):
        """
        Convert an amount from base currency to target currency.
        
        Args:
            base_currency (str): Base currency code
            target_currency (str): Target currency code
            amount (float): Amount to convert
            
        Returns:
            float: Converted amount
        """
        try:
            rates = self.get_exchange_rate(base_currency)
            if target_currency in rates:
                return amount * rates[target_currency]
            else:
                raise Exception(f"Currency '{target_currency}' not found")
        except Exception as e:
            raise Exception(f"Conversion error: {e}")
    
    def get_historical_rates(self, base_currency, target_currency, days=7):
        """
        Get historical exchange rates for plotting trends.
        
        Args:
            base_currency (str): Base currency code
            target_currency (str): Target currency code
            days (int): Number of days to look back
            
        Returns:
            tuple: (dates, rates) lists for plotting
        """
        dates = []
        rates = []
        
        # Get today's rate
        try:
            current_rates = self.get_exchange_rate(base_currency)
            if target_currency in current_rates:
                today = datetime.now()
                dates.append(today.strftime("%Y-%m-%d"))
                rates.append(current_rates[target_currency])
                
                # Try to get historical data for the past days
                for i in range(1, days):
                    date = today - timedelta(days=i)
                    date_str = date.strftime("%Y-%m-%d")
                    hist_file = os.path.join(self.historical_dir, f"{base_currency}_{date_str}.json")
                    
                    if os.path.exists(hist_file):
                        with open(hist_file, "r") as f:
                            data = json.load(f)
                            if target_currency in data["rates"]:
                                dates.append(date_str)
                                rates.append(data["rates"][target_currency])
                                
        except Exception as e:
            print(f"Error getting historical rates: {e}")
            
        # Return available data (might be less than requested days)
        return list(reversed(dates)), list(reversed(rates))


class CurrencyConverterApp:
    """
    Advanced Currency Converter Application with GUI and visualization features.
    """
    
    def __init__(self, root):
        """Initialize the application GUI."""
        self.root = root
        self.root.title("Advanced Currency Converter")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Initialize converter
        self.converter = CurrencyConverter()
        
        # Set up variables
        self.base_currency = tk.StringVar(value="USD")
        self.target_currency = tk.StringVar(value="EUR")
        self.amount = tk.DoubleVar(value=1.0)
        self.result = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")
        
        # Create favorites dictionary
        self.favorites = self._load_favorites()
        
        # Set up the UI
        self._create_widgets()
        
        # Initial conversion
        self.convert()
    
    def _load_favorites(self):
        """Load saved favorite currency pairs."""
        favorites_file = os.path.join(self.converter.cache_dir, "favorites.json")
        if os.path.exists(favorites_file):
            try:
                with open(favorites_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_favorites(self):
        """Save favorite currency pairs."""
        favorites_file = os.path.join(self.converter.cache_dir, "favorites.json")
        with open(favorites_file, "w") as f:
            json.dump(self.favorites, f)
    
    def _create_widgets(self):
        """Create and arrange UI widgets."""
        # Main container with tabs
        self.tab_control = ttk.Notebook(self.root)
        
        # Converter tab
        self.converter_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.converter_tab, text="Converter")
        
        # Charts tab
        self.charts_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.charts_tab, text="Historical Charts")
        
        # Favorites tab
        self.favorites_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.favorites_tab, text="Favorites")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Set up each tab
        self._setup_converter_tab()
        self._setup_charts_tab()
        self._setup_favorites_tab()
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Label(status_frame, textvariable=self.status).pack(side=tk.LEFT, padx=10)
        ttk.Label(
            status_frame, 
            text="Data source: ExchangeRate-API"
        ).pack(side=tk.RIGHT, padx=10)
    
    def _setup_converter_tab(self):
        """Set up the main converter tab UI."""
        frame = ttk.Frame(self.converter_tab, padding="20")
        frame.pack(fill="both", expand=True)
        
        # Currency selection
        ttk.Label(frame, text="From Currency:").grid(row=0, column=0, sticky=tk.W, pady=5)
        from_combo = ttk.Combobox(
            frame, 
            textvariable=self.base_currency, 
            values=self.converter.currencies,
            state="readonly"
        )
        from_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        from_combo.bind("<<ComboboxSelected>>", lambda e: self.convert())
        
        ttk.Label(frame, text="To Currency:").grid(row=1, column=0, sticky=tk.W, pady=5)
        to_combo = ttk.Combobox(
            frame, 
            textvariable=self.target_currency, 
            values=self.converter.currencies,
            state="readonly"
        )
        to_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        to_combo.bind("<<ComboboxSelected>>", lambda e: self.convert())
        
        # Swap button
        ttk.Button(
            frame, 
            text="⇅ Swap", 
            command=self.swap_currencies
        ).grid(row=0, column=2, rowspan=2, padx=10)
        
        # Amount input
        ttk.Label(frame, text="Amount:").grid(row=2, column=0, sticky=tk.W, pady=5)
        amount_entry = ttk.Entry(frame, textvariable=self.amount, width=15)
        amount_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        amount_entry.bind("<Return>", lambda e: self.convert())
        
        # Convert button
        ttk.Button(
            frame, 
            text="Convert", 
            command=self.convert
        ).grid(row=3, column=1, sticky=tk.W, pady=10)
        
        # Add to favorites button
        ttk.Button(
            frame, 
            text="Add to Favorites", 
            command=self.add_to_favorites
        ).grid(row=3, column=2, sticky=tk.W, pady=10)
        
        # Result display
        result_frame = ttk.LabelFrame(frame, text="Conversion Result")
        result_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)
        
        ttk.Label(
            result_frame, 
            textvariable=self.result, 
            font=("Arial", 14)
        ).pack(pady=10, padx=10)
        
        # Rate display
        self.rate_var = tk.StringVar(value="")
        ttk.Label(
            result_frame, 
            textvariable=self.rate_var
        ).pack(pady=5, padx=10)
    
    def _setup_charts_tab(self):
        """Set up the historical charts tab UI."""
        frame = ttk.Frame(self.charts_tab, padding="20")
        frame.pack(fill="both", expand=True)
        
        # Currency selection for chart
        selection_frame = ttk.Frame(frame)
        selection_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(selection_frame, text="Base Currency:").grid(row=0, column=0, padx=5)
        ttk.Combobox(
            selection_frame, 
            textvariable=self.base_currency, 
            values=self.converter.currencies,
            state="readonly",
            width=10
        ).grid(row=0, column=1, padx=5)
        
        ttk.Label(selection_frame, text="Target Currency:").grid(row=0, column=2, padx=5)
        ttk.Combobox(
            selection_frame, 
            textvariable=self.target_currency, 
            values=self.converter.currencies,
            state="readonly",
            width=10
        ).grid(row=0, column=3, padx=5)
        
        # Time range selection
        self.days_var = tk.IntVar(value=7)
        ttk.Label(selection_frame, text="Time Range:").grid(row=0, column=4, padx=5)
        ttk.Combobox(
            selection_frame, 
            textvariable=self.days_var, 
            values=[7, 14, 30, 90],
            state="readonly",
            width=10
        ).grid(row=0, column=5, padx=5)
        
        # Chart button
        ttk.Button(
            selection_frame, 
            text="Generate Chart", 
            command=self.generate_chart
        ).grid(row=0, column=6, padx=10)
        
        # Chart area
        self.chart_frame = ttk.Frame(frame)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Initial message
        ttk.Label(
            self.chart_frame, 
            text="Select currencies and time range, then click 'Generate Chart'",
            font=("Arial", 12)
        ).pack(pady=50)
    
    def _setup_favorites_tab(self):
        """Set up the favorites tab UI."""
        frame = ttk.Frame(self.favorites_tab, padding="20")
        frame.pack(fill="both", expand=True)
        
        # Title
        ttk.Label(
            frame, 
            text="Saved Currency Pairs", 
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        # Favorites list frame
        self.favorites_list_frame = ttk.Frame(frame)
        self.favorites_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Refresh favorites list
        self._refresh_favorites_list()
    
    def _refresh_favorites_list(self):
        """Refresh the list of favorite currency pairs."""
        # Clear existing widgets
        for widget in self.favorites_list_frame.winfo_children():
            widget.destroy()
        
        # No favorites message
        if not self.favorites:
            ttk.Label(
                self.favorites_list_frame, 
                text="No favorites saved. Add some from the Converter tab.",
                font=("Arial", 12)
            ).pack(pady=50)
            return
        
        # Create headers
        headers_frame = ttk.Frame(self.favorites_list_frame)
        headers_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(headers_frame, text="Currency Pair", width=15, font=("Arial", 11, "bold")).grid(row=0, column=0, padx=5)
        ttk.Label(headers_frame, text="Exchange Rate", width=15, font=("Arial", 11, "bold")).grid(row=0, column=1, padx=5)
        ttk.Label(headers_frame, text="Last Updated", width=20, font=("Arial", 11, "bold")).grid(row=0, column=2, padx=5)
        ttk.Label(headers_frame, text="Actions", width=15, font=("Arial", 11, "bold")).grid(row=0, column=3, padx=5)
        
        # Add separator
        ttk.Separator(self.favorites_list_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # List of favorites with buttons
        list_container = ttk.Frame(self.favorites_list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        for favorite_id, favorite in self.favorites.items():
            item_frame = ttk.Frame(list_container)
            item_frame.pack(fill=tk.X, pady=2)
            
            # Currency pair
            pair_text = f"{favorite['base']} → {favorite['target']}"
            ttk.Label(item_frame, text=pair_text, width=15).grid(row=row, column=0, padx=5)
            
            # Get current rate
            rate_text = "Loading..."
            try:
                threading.Thread(
                    target=self._update_favorite_rate,
                    args=(item_frame, row, favorite['base'], favorite['target'])
                ).start()
            except Exception:
                rate_text = "Error"
            
            ttk.Label(item_frame, text=rate_text, width=15).grid(row=row, column=1, padx=5)
            
            # Last updated
            last_updated = datetime.fromtimestamp(favorite['timestamp']).strftime("%Y-%m-%d %H:%M")
            ttk.Label(item_frame, text=last_updated, width=20).grid(row=row, column=2, padx=5)
            
            # Actions
            actions_frame = ttk.Frame(item_frame)
            actions_frame.grid(row=row, column=3, padx=5)
            
            ttk.Button(
                actions_frame, 
                text="Use", 
                width=6,
                command=lambda b=favorite['base'], t=favorite['target']: self._use_favorite(b, t)
            ).grid(row=0, column=0, padx=2)
            
            ttk.Button(
                actions_frame, 
                text="Delete", 
                width=6,
                command=lambda fid=favorite_id: self._delete_favorite(fid)
            ).grid(row=0, column=1, padx=2)
            
            row += 1
    
    def _update_favorite_rate(self, parent_frame, row, base, target):
        """Update the rate display for a favorite pair."""
        try:
            rates = self.converter.get_exchange_rate(base)
            if target in rates:
                rate = rates[target]
                rate_label = ttk.Label(parent_frame, text=f"{rate:.4f}", width=15)
                rate_label.grid(row=row, column=1, padx=5)
        except Exception:
            rate_label = ttk.Label(parent_frame, text="Error", width=15)
            rate_label.grid(row=row, column=1, padx=5)
    
    def _use_favorite(self, base, target):
        """Use a favorite currency pair for conversion."""
        self.base_currency.set(base)
        self.target_currency.set(target)
        self.tab_control.select(0)  # Switch to converter tab
        self.convert()
    
    def _delete_favorite(self, favorite_id):
        """Delete a favorite currency pair."""
        if favorite_id in self.favorites:
            del self.favorites[favorite_id]
            self._save_favorites()
            self._refresh_favorites_list()
    
    def convert(self):
        """Perform currency conversion and update display."""
        base = self.base_currency.get()
        target = self.target_currency.get()
        
        try:
            amount = self.amount.get()
        except tk.TclError:
            amount = 0
            self.amount.set(0)
        
        self.status.set("Converting...")
        self.root.update_idletasks()
        
        try:
            converted = self.converter.convert_currency(base, target, amount)
            self.result.set(f"{amount:.2f} {base} = {converted:.2f} {target}")
            
            # Display exchange rate
            rates = self.converter.get_exchange_rate(base)
            rate = rates[target]
            self.rate_var.set(f"Exchange Rate: 1 {base} = {rate:.4f} {target}")
            
            self.status.set("Ready")
        except Exception as e:
            self.result.set(f"Error: {str(e)}")
            self.rate_var.set("")
            self.status.set("Error occurred")
    
    def swap_currencies(self):
        """Swap base and target currencies."""
        base = self.base_currency.get()
        target = self.target_currency.get()
        
        self.base_currency.set(target)
        self.target_currency.set(base)
        
        self.convert()
    
    def add_to_favorites(self):
        """Add current currency pair to favorites."""
        base = self.base_currency.get()
        target = self.target_currency.get()
        
        # Create a unique ID for this pair
        favorite_id = f"{base}_{target}"
        
        # Check if already exists
        if favorite_id in self.favorites:
            messagebox.showinfo("Already Saved", "This currency pair is already in your favorites.")
            return
        
        # Add to favorites
        self.favorites[favorite_id] = {
            "base": base,
            "target": target,
            "timestamp": time.time()
        }
        
        # Save to file
        self._save_favorites()
        
        # Show confirmation
        messagebox.showinfo("Favorite Added", f"Added {base} → {target} to favorites.")
        
        # Refresh favorites tab if it's visible
        if self.tab_control.index("current") == 2:  # Favorites tab
            self._refresh_favorites_list()
    
    def generate_chart(self):
        """Generate and display historical exchange rate chart."""
        base = self.base_currency.get()
        target = self.target_currency.get()
        days = self.days_var.get()
        
        # Clear current chart
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        # Show loading message
        loading_label = ttk.Label(self.chart_frame, text="Loading data...", font=("Arial", 12))
        loading_label.pack(pady=50)
        self.root.update_idletasks()
        
        try:
            # Get historical data
            dates, rates = self.converter.get_historical_rates(base, target, days)
            
            if not dates or not rates:
                loading_label.config(text="Not enough historical data available.\nUse the app for a few days to collect data.")
                return
            
            # Remove loading message
            loading_label.destroy()
            
            # Create figure and plot
            fig = plt.Figure(figsize=(8, 4), dpi=100)
            ax = fig.add_subplot(111)
            
            # Plot data
            ax.plot(dates, rates, marker='o', linestyle='-', linewidth=2, markersize=6)
            
            # Format plot
            ax.set_title(f"{base} to {target} Exchange Rate - Last {len(dates)} Days")
            ax.set_ylabel(f"1 {base} in {target}")
            ax.set_xlabel("Date")
            
            # Format x-axis labels
            if len(dates) > 10:
                # Show fewer x-axis labels to avoid crowding
                step = len(dates) // 5
                ax.set_xticks(dates[::step])
                ax.set_xticklabels(dates[::step], rotation=45)
            else:
                ax.set_xticks(dates)
                ax.set_xticklabels(dates, rotation=45)
            
            ax.grid(True, linestyle='--', alpha=0.7)
            fig.tight_layout()
            
            # Create canvas
            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            loading_label.config(text=f"Error generating chart: {str(e)}")
            print(f"Chart error: {e}")


if __name__ == "__main__":
    # Set up the application
    root = tk.Tk()
    app = CurrencyConverterApp(root)
    
    # Start the main loop
    root.mainloop()