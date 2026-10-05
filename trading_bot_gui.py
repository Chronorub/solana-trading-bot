#!/usr/bin/env python3
"""
Chronorub Advanced Trading Bot GUI
- Tkinter-based GUI with live memecoin scanner
- Color-coded alerts for snipe opportunities
- Full wallet manager with private key export
- Address book functionality
- Solana/Polygon/Base/PumpFun support
"""

import os
import sys
import json
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

# Blockchain imports
try:
    from solders.keypair import Keypair
    from solders.pubkey import PublicKey
    from solana.rpc.api import Client as SolanaClient
except ImportError:
    os.system("python -m pip install solders solana")
    from solders.keypair import Keypair
    from solders.pubkey import PublicKey
    from solana.rpc.api import Client as SolanaClient

try:
    from web3 import Web3
except ImportError:
    os.system("python -m pip install web3")
    from web3 import Web3

try:
    import requests
except ImportError:
    os.system("python -m pip install requests")
    import requests


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "DONATION_LINK": "https://cash.app/$Chronorub",
    "SOL_RPC": "https://api.mainnet-beta.solana.com",
    "POLYGON_RPC": "https://polygon-rpc.com",
    "BASE_RPC": "https://mainnet.base.org",
    "PUMPFUN_URL": "https://frontend-api.pump.fun",
    "REFRESH_INTERVAL": 3,  # seconds
    "SNIPE_WATCH_INTERVAL": 5,  # seconds
}

COLORS = {
    "bg_dark": "#0a0e27",
    "bg_darker": "#060812",
    "fg_text": "#e0e0e0",
    "accent_green": "#00ff41",
    "accent_red": "#ff1744",
    "accent_yellow": "#ffc300",
    "accent_blue": "#00bfff",
    "accent_purple": "#da70d6",
    "snipe": "#00ff41",  # Green for snipe-ready
    "watch": "#ffc300",  # Yellow for watch
    "alert": "#ff1744",  # Red for alert
    "neutral": "#00bfff",  # Blue for neutral
}


# ============================================================================
# DATA MANAGERS
# ============================================================================

class WalletManager:
    """Manages wallet generation and persistence"""
    
    def __init__(self):
        self.wallets_file = "wallets.json"
        self.address_book_file = "address_book.json"
        self.wallets = self.load_wallets()
        self.address_book = self.load_address_book()
    
    def load_wallets(self) -> Dict:
        """Load wallets from JSON file"""
        if os.path.exists(self.wallets_file):
            try:
                with open(self.wallets_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_wallets(self):
        """Persist wallets to JSON file"""
        with open(self.wallets_file, "w", encoding="utf-8") as f:
            json.dump(self.wallets, f, indent=2)
    
    def load_address_book(self) -> Dict:
        """Load address book from JSON file"""
        if os.path.exists(self.address_book_file):
            try:
                with open(self.address_book_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_address_book(self):
        """Persist address book to JSON file"""
        with open(self.address_book_file, "w", encoding="utf-8") as f:
            json.dump(self.address_book, f, indent=2)
    
    def generate_solana_wallet(self) -> Dict:
        """Generate new Solana keypair"""
        kp = Keypair()
        return {
            "chain": "solana",
            "address": str(kp.pubkey()),
            "private_key": kp.secret().hex(),
            "created_at": datetime.now().isoformat(),
        }
    
    def generate_evm_wallet(self) -> Dict:
        """Generate new EVM-compatible wallet"""
        w3 = Web3()
        account = w3.eth.account.create()
        return {
            "chain": "evm",
            "address": account.address,
            "private_key": account._private_key.hex(),
            "created_at": datetime.now().isoformat(),
        }
    
    def add_wallet(self, chain: str) -> Optional[Dict]:
        """Add new wallet"""
        try:
            if chain.lower() == "solana":
                wallet = self.generate_solana_wallet()
            elif chain.lower() == "evm":
                wallet = self.generate_evm_wallet()
            else:
                return None
            
            wallet_id = f"{chain.lower()}_{len(self.wallets) + 1}"
            self.wallets[wallet_id] = wallet
            self.save_wallets()
            return wallet
        except Exception as e:
            print(f"Error generating wallet: {e}")
            return None
    
    def delete_wallet(self, wallet_id: str) -> bool:
        """Delete wallet by ID"""
        if wallet_id in self.wallets:
            del self.wallets[wallet_id]
            self.save_wallets()
            return True
        return False
    
    def save_address(self, label: str, address: str, chain: str, notes: str = "") -> bool:
        """Save address to address book"""
        try:
            self.address_book[label] = {
                "address": address,
                "chain": chain,
                "notes": notes,
                "saved_at": datetime.now().isoformat(),
            }
            self.save_address_book()
            return True
        except Exception as e:
            print(f"Error saving address: {e}")
            return False
    
    def delete_address(self, label: str) -> bool:
        """Delete address from address book"""
        if label in self.address_book:
            del self.address_book[label]
            self.save_address_book()
            return True
        return False
    
    def get_all_wallets(self) -> List[Dict]:
        """Return all wallets"""
        return list(self.wallets.items())
    
    def get_all_addresses(self) -> List[Dict]:
        """Return all saved addresses"""
        return list(self.address_book.items())


class BalanceTracker:
    """Track balances across chains"""
    
    def __init__(self):
        try:
            self.solana_client = SolanaClient(CONFIG["SOL_RPC"])
        except:
            self.solana_client = None
        
        self.polygon_w3 = Web3(Web3.HTTPProvider(CONFIG["POLYGON_RPC"]))
        self.base_w3 = Web3(Web3.HTTPProvider(CONFIG["BASE_RPC"]))
        self.balances = {}
    
    def get_sol_balance(self, address: str) -> float:
        """Get SOL balance"""
        try:
            if not self.solana_client:
                return 0.0
            pubkey = PublicKey(address)
            res = self.solana_client.get_balance(pubkey)
            return float(res.value / 1_000_000_000)
        except:
            return 0.0
    
    def get_polygon_balance(self, address: str) -> float:
        """Get MATIC balance"""
        try:
            wei = self.polygon_w3.eth.get_balance(address)
            return float(self.polygon_w3.from_wei(wei, "ether"))
        except:
            return 0.0
    
    def get_base_balance(self, address: str) -> float:
        """Get BASE ETH balance"""
        try:
            wei = self.base_w3.eth.get_balance(address)
            return float(self.base_w3.from_wei(wei, "ether"))
        except:
            return 0.0
    
    def update_all_balances(self, wallets: Dict) -> Dict:
        """Update balances for all wallets"""
        balances = {}
        for wallet_id, wallet in wallets.items():
            if wallet.get("chain") == "solana":
                balance = self.get_sol_balance(wallet["address"])
                balances[wallet_id] = {
                    "chain": "Solana",
                    "symbol": "SOL",
                    "balance": balance,
                }
            else:
                poly = self.get_polygon_balance(wallet["address"])
                base = self.get_base_balance(wallet["address"])
                balances[f"{wallet_id}_poly"] = {
                    "chain": "Polygon",
                    "symbol": "MATIC",
                    "balance": poly,
                }
                balances[f"{wallet_id}_base"] = {
                    "chain": "Base",
                    "symbol": "ETH",
                    "balance": base,
                }
        self.balances = balances
        return balances


class PumpFunScanner:
    """Scan PumpFun for snipe opportunities"""
    
    def __init__(self):
        self.last_scanned = {}
    
    def get_launches(self, limit: int = 20) -> List[Dict]:
        """Fetch latest token launches"""
        try:
            url = f"{CONFIG['PUMPFUN_URL']}/api/public/all?sort=created&limit={limit}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []
    
    def evaluate_token(self, token: Dict) -> Dict:
        """Evaluate token for snipe opportunity"""
        try:
            market_cap = float(token.get("marketCap", 0))
            liquidity = float(token.get("liquidity", 0))
            holders = int(token.get("holders", 0))
            volume = float(token.get("volume24h", 0))
            
            score = 0
            status = "WATCH"
            
            # Scoring system
            if market_cap < 10000:
                score += 3
                status = "SNIPE"
            elif market_cap < 50000:
                score += 2
                status = "SNIPE"
            elif market_cap < 100000:
                score += 1
                status = "WATCH"
            
            if liquidity > 500:
                score += 1
            if holders > 10:
                score += 1
            
            return {
                "token": token,
                "status": status,
                "score": score,
                "market_cap": market_cap,
                "liquidity": liquidity,
                "holders": holders,
                "volume": volume,
            }
        except:
            return {
                "token": token,
                "status": "ERROR",
                "score": 0,
                "market_cap": 0,
                "liquidity": 0,
                "holders": 0,
                "volume": 0,
            }


# ============================================================================
# GUI APPLICATION
# ============================================================================

class TradingBotGUI:
    """Advanced Tkinter GUI for trading bot"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Chronorub Trading Bot - Advanced GUI")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_dark"])
        
        # Initialize managers
        self.wallet_manager = WalletManager()
        self.balance_tracker = BalanceTracker()
        self.scanner = PumpFunScanner()
        
        # Threading
        self.update_queue = queue.Queue()
        self.running = True
        self.scanner_thread = None
        
        # Setup GUI
        self.setup_styles()
        self.create_widgets()
        self.start_background_tasks()
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TFrame', background=COLORS["bg_dark"])
        style.configure('TLabel', background=COLORS["bg_dark"], foreground=COLORS["fg_text"])
        style.configure('TButton', background=COLORS["accent_blue"], foreground=COLORS["bg_dark"])
        style.configure('Heading.TLabel', font=("Arial", 14, "bold"), background=COLORS["bg_dark"], foreground=COLORS["accent_green"])
        style.configure('Treeview', background=COLORS["bg_darker"], foreground=COLORS["fg_text"], fieldbackground=COLORS["bg_darker"])
    
    def create_widgets(self):
        """Create main GUI layout"""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_label = ttk.Label(header_frame, text="⚡ CHRONORUB TRADING BOT", style='Heading.TLabel')
        title_label.pack(side=tk.LEFT)
        
        donation_label = ttk.Label(header_frame, text="💰 " + CONFIG["DONATION_LINK"], foreground=COLORS["accent_green"])
        donation_label.pack(side=tk.RIGHT)
        
        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tabs
        self.create_dashboard_tab()
        self.create_wallet_tab()
        self.create_scanner_tab()
        self.create_address_book_tab()
    
    def create_dashboard_tab(self):
        """Dashboard with stats and balances"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Dashboard")
        
        # Stats frame
        stats_frame = ttk.LabelFrame(frame, text="Account Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.stats_labels = {}
        stats = [
            ("Total Wallets", "total_wallets"),
            ("Solana Wallets", "sol_wallets"),
            ("EVM Wallets", "evm_wallets"),
            ("Total SOL", "total_sol"),
            ("Total MATIC", "total_matic"),
            ("Total BASE ETH", "total_eth"),
        ]
        
        for i, (label_text, key) in enumerate(stats):
            label = ttk.Label(stats_frame, text=f"{label_text}:", foreground=COLORS["accent_green"])
            label.grid(row=i // 3, column=(i % 3) * 2, sticky=tk.W, padx=10, pady=5)
            
            value_label = ttk.Label(stats_frame, text="0", foreground=COLORS["accent_blue"])
            value_label.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky=tk.E, padx=10, pady=5)
            
            self.stats_labels[key] = value_label
        
        # Balances frame
        balance_frame = ttk.LabelFrame(frame, text="Wallet Balances", padding=10)
        balance_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for balances
        columns = ("Wallet ID", "Chain", "Address", "Balance", "Symbol")
        self.balance_tree = ttk.Treeview(balance_frame, columns=columns, height=15)
        self.balance_tree.heading('#0', text='#')
        self.balance_tree.column('#0', width=30)
        
        for col in columns:
            self.balance_tree.heading(col, text=col)
            self.balance_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(balance_frame, orient=tk.VERTICAL, command=self.balance_tree.yview)
        self.balance_tree.configure(yscrollcommand=scrollbar.set)
        
        self.balance_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        refresh_btn = ttk.Button(frame, text="Refresh Balances", command=self.refresh_balances)
        refresh_btn.pack(pady=10)
    
    def create_wallet_tab(self):
        """Wallet management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Wallet Manager")
        
        # Generation frame
        gen_frame = ttk.LabelFrame(frame, text="Generate New Wallet", padding=10)
        gen_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(gen_frame, text="Generate Solana Wallet", command=lambda: self.generate_wallet("solana")).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_frame, text="Generate EVM Wallet", command=lambda: self.generate_wallet("evm")).pack(side=tk.LEFT, padx=5)
        
        # Wallets list frame
        list_frame = ttk.LabelFrame(frame, text="Your Wallets", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("ID", "Chain", "Address", "Created")
        self.wallet_tree = ttk.Treeview(list_frame, columns=columns, height=12)
        self.wallet_tree.heading('#0', text='#')
        self.wallet_tree.column('#0', width=30)
        
        for col in columns:
            self.wallet_tree.heading(col, text=col)
            self.wallet_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.wallet_tree.yview)
        self.wallet_tree.configure(yscrollcommand=scrollbar.set)
        
        self.wallet_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action frame
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(action_frame, text="View Details", command=self.view_wallet_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Export Private Key", command=self.export_private_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete Wallet", command=self.delete_wallet).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Export All Wallets", command=self.export_all_wallets).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", command=self.refresh_wallet_list).pack(side=tk.LEFT, padx=5)
        
        # Initial load
        self.refresh_wallet_list()
    
    def create_scanner_tab(self):
        """Live memecoin scanner tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Memecoin Scanner")
        
        # Control frame
        control_frame = ttk.LabelFrame(frame, text="Scanner Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(control_frame, text="Start Scan", command=self.start_scanner).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Scan", command=self.stop_scanner).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh Now", command=self.scan_once).pack(side=tk.LEFT, padx=5)
        
        # Scan results frame
        results_frame = ttk.LabelFrame(frame, text="Scan Results (Color-Coded)", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview with custom tags for colors
        columns = ("Status", "Name", "Market Cap", "Liquidity", "Holders", "Volume", "Mint")
        self.scanner_tree = ttk.Treeview(results_frame, columns=columns, height=15)
        self.scanner_tree.heading('#0', text='Score')
        self.scanner_tree.column('#0', width=50)
        
        for col in columns:
            self.scanner_tree.heading(col, text=col)
            self.scanner_tree.column(col, width=110)
        
        # Define tags for color-coding
        self.scanner_tree.tag_configure('snipe', background=COLORS["bg_darker"], foreground=COLORS["snipe"])
        self.scanner_tree.tag_configure('watch', background=COLORS["bg_darker"], foreground=COLORS["watch"])
        self.scanner_tree.tag_configure('alert', background=COLORS["bg_darker"], foreground=COLORS["alert"])
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.scanner_tree.yview)
        self.scanner_tree.configure(yscrollcommand=scrollbar.set)
        
        self.scanner_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Legend
        legend_frame = ttk.Frame(frame)
        legend_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(legend_frame, text="🟢 SNIPE = Green (Cap < $50K, Good Liquidity)", foreground=COLORS["snipe"]).pack(side=tk.LEFT, padx=5)
        ttk.Label(legend_frame, text="🟡 WATCH = Yellow (Monitor)", foreground=COLORS["watch"]).pack(side=tk.LEFT, padx=5)
        ttk.Label(legend_frame, text="🔴 ALERT = Red (High Risk)", foreground=COLORS["alert"]).pack(side=tk.LEFT, padx=5)
    
    def create_address_book_tab(self):
        """Saved addresses tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Address Book")
        
        # Add address frame
        add_frame = ttk.LabelFrame(frame, text="Add New Address", padding=10)
        add_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(add_frame, text="Label:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.addr_label_entry = ttk.Entry(add_frame, width=30)
        self.addr_label_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(add_frame, text="Address:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.addr_address_entry = ttk.Entry(add_frame, width=30)
        self.addr_address_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(add_frame, text="Chain:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.addr_chain_combo = ttk.Combobox(add_frame, values=["Solana", "Polygon", "Base"], width=28, state='readonly')
        self.addr_chain_combo.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(add_frame, text="Notes:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.addr_notes_entry = ttk.Entry(add_frame, width=30)
        self.addr_notes_entry.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Button(add_frame, text="Save Address", command=self.save_address).grid(row=4, column=1, sticky=tk.E, padx=5, pady=10)
        
        # Address list frame
        list_frame = ttk.LabelFrame(frame, text="Saved Addresses", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("Label", "Address", "Chain", "Notes")
        self.address_tree = ttk.Treeview(list_frame, columns=columns, height=12)
        self.address_tree.heading('#0', text='#')
        self.address_tree.column('#0', width=30)
        
        for col in columns:
            self.address_tree.heading(col, text=col)
            self.address_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.address_tree.yview)
        self.address_tree.configure(yscrollcommand=scrollbar.set)
        
        self.address_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action frame
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(action_frame, text="Delete Address", command=self.delete_address).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", command=self.refresh_address_book).pack(side=tk.LEFT, padx=5)
        
        # Initial load
        self.refresh_address_book()
    
    # ========================================================================
    # CALLBACK METHODS
    # ========================================================================
    
    def generate_wallet(self, chain: str):
        """Generate new wallet"""
        wallet = self.wallet_manager.add_wallet(chain)
        if wallet:
            messagebox.showinfo("Success", f"New {chain.upper()} wallet created!\n\nAddress:\n{wallet['address']}")
            self.refresh_wallet_list()
            self.refresh_balances()
        else:
            messagebox.showerror("Error", "Failed to generate wallet")
    
    def refresh_wallet_list(self):
        """Refresh wallet tree"""
        for item in self.wallet_tree.get_children():
            self.wallet_tree.delete(item)
        
        for idx, (wallet_id, wallet) in enumerate(self.wallet_manager.get_all_wallets(), start=1):
            chain = wallet.get("chain", "unknown").upper()
            address = wallet["address"][:10] + "..." + wallet["address"][-8:]
            created = wallet.get("created_at", "").split("T")[0]
            
            self.wallet_tree.insert("", "end", text=str(idx), values=(wallet_id, chain, address, created))
    
    def view_wallet_details(self):
        """View selected wallet details"""
        selection = self.wallet_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a wallet")
            return
        
        item = selection[0]
        wallet_id = self.wallet_tree.item(item)['values'][0]
        wallet = self.wallet_manager.wallets.get(wallet_id)
        
        if not wallet:
            messagebox.showerror("Error", "Wallet not found")
            return
        
        details = f"Wallet ID: {wallet_id}\n"
        details += f"Chain: {wallet.get('chain', 'N/A').upper()}\n"
        details += f"Address: {wallet['address']}\n"
        details += f"Created: {wallet.get('created_at', 'N/A')}\n\n"
        details += f"Private Key (KEEP SAFE!):\n{wallet['private_key']}\n\n"
        details += "WARNING: Never share your private key!"
        
        messagebox.showinfo("Wallet Details", details)
    
    def export_private_key(self):
        """Export single private key"""
        selection = self.wallet_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a wallet")
            return
        
        item = selection[0]
        wallet_id = self.wallet_tree.item(item)['values'][0]
        wallet = self.wallet_manager.wallets.get(wallet_id)
        
        if not wallet:
            messagebox.showerror("Error", "Wallet not found")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{wallet_id}_private_key.txt"
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"Wallet: {wallet_id}\n")
                    f.write(f"Chain: {wallet.get('chain').upper()}\n")
                    f.write(f"Address: {wallet['address']}\n")
                    f.write(f"Created: {wallet.get('created_at')}\n\n")
                    f.write(f"PRIVATE KEY:\n{wallet['private_key']}\n\n")
                    f.write("WARNING: This is a sensitive file. Keep it secure and never share!")
                messagebox.showinfo("Success", f"Private key exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def delete_wallet(self):
        """Delete selected wallet"""
        selection = self.wallet_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a wallet")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this wallet?"):
            item = selection[0]
            wallet_id = self.wallet_tree.item(item)['values'][0]
            self.wallet_manager.delete_wallet(wallet_id)
            self.refresh_wallet_list()
            messagebox.showinfo("Success", "Wallet deleted")
    
    def export_all_wallets(self):
        """Export all wallets to JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"wallets_backup_{int(time.time())}.json"
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(self.wallet_manager.wallets, f, indent=2)
                messagebox.showinfo("Success", f"All wallets exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def refresh_balances(self):
        """Refresh all balances"""
        for item in self.balance_tree.get_children():
            self.balance_tree.delete(item)
        
        balances = self.balance_tracker.update_all_balances(self.wallet_manager.wallets)
        
        for idx, (balance_id, balance_info) in enumerate(balances.items(), start=1):
            chain = balance_info.get("chain", "N/A")
            symbol = balance_info.get("symbol", "N/A")
            balance = balance_info.get("balance", 0)
            
            self.balance_tree.insert("", "end", text=str(idx), values=(balance_id, chain, "...", f"{balance:.6f}", symbol))
        
        self.update_stats()
    
    def update_stats(self):
        """Update statistics labels"""
        wallets = self.wallet_manager.wallets
        balances = self.balance_tracker.balances
        
        sol_wallets = sum(1 for w in wallets.values() if w.get("chain") == "solana")
        evm_wallets = len(wallets) - sol_wallets
        
        total_sol = sum(b.get("balance", 0) for k, b in balances.items() if b.get("symbol") == "SOL")
        total_matic = sum(b.get("balance", 0) for k, b in balances.items() if b.get("symbol") == "MATIC")
        total_eth = sum(b.get("balance", 0) for k, b in balances.items() if b.get("symbol") == "ETH")
        
        self.stats_labels["total_wallets"].config(text=str(len(wallets)))
        self.stats_labels["sol_wallets"].config(text=str(sol_wallets))
        self.stats_labels["evm_wallets"].config(text=str(evm_wallets))
        self.stats_labels["total_sol"].config(text=f"{total_sol:.6f}")
        self.stats_labels["total_matic"].config(text=f"{total_matic:.6f}")
        self.stats_labels["total_eth"].config(text=f"{total_eth:.6f}")
    
    def save_address(self):
        """Save address to address book"""
        label = self.addr_label_entry.get().strip()
        address = self.addr_address_entry.get().strip()
        chain = self.addr_chain_combo.get()
        notes = self.addr_notes_entry.get().strip()
        
        if not all([label, address, chain]):
            messagebox.showwarning("Warning", "Please fill in all required fields")
            return
        
        if self.wallet_manager.save_address(label, address, chain, notes):
            messagebox.showinfo("Success", "Address saved")
            self.addr_label_entry.delete(0, tk.END)
            self.addr_address_entry.delete(0, tk.END)
            self.addr_notes_entry.delete(0, tk.END)
            self.refresh_address_book()
        else:
            messagebox.showerror("Error", "Failed to save address")
    
    def delete_address(self):
        """Delete selected address"""
        selection = self.address_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an address")
            return
        
        if messagebox.askyesno("Confirm", "Delete this address?"):
            item = selection[0]
            label = self.address_tree.item(item)['values'][0]
            self.wallet_manager.delete_address(label)
            self.refresh_address_book()
            messagebox.showinfo("Success", "Address deleted")
    
    def refresh_address_book(self):
        """Refresh address book tree"""
        for item in self.address_tree.get_children():
            self.address_tree.delete(item)
        
        for idx, (label, addr_info) in enumerate(self.wallet_manager.get_all_addresses(), start=1):
            address = addr_info["address"][:10] + "..." + addr_info["address"][-8:]
            chain = addr_info.get("chain", "N/A")
            notes = addr_info.get("notes", "")
            
            self.address_tree.insert("", "end", text=str(idx), values=(label, address, chain, notes))
    
    def start_scanner(self):
        """Start background scanner thread"""
        if self.scanner_thread is None or not self.scanner_thread.is_alive():
            self.running = True
            self.scanner_thread = threading.Thread(target=self.scanner_worker, daemon=True)
            self.scanner_thread.start()
            messagebox.showinfo("Scanner", "Scanner started")
    
    def stop_scanner(self):
        """Stop background scanner"""
        self.running = False
        messagebox.showinfo("Scanner", "Scanner stopped")
    
    def scan_once(self):
        """Scan PumpFun once"""
        threading.Thread(target=self._scan_pumpfun, daemon=True).start()
    
    def _scan_pumpfun(self):
        """Perform single scan"""
        launches = self.scanner.get_launches(20)
        self.root.after(0, lambda: self.display_scan_results(launches))
    
    def scanner_worker(self):
        """Background scanner worker"""
        while self.running:
            launches = self.scanner.get_launches(20)
            self.root.after(0, lambda l=launches: self.display_scan_results(l))
            time.sleep(CONFIG["SNIPE_WATCH_INTERVAL"])
    
    def display_scan_results(self, launches: List[Dict]):
        """Display scan results in tree"""
        for item in self.scanner_tree.get_children():
            self.scanner_tree.delete(item)
        
        for launch in launches:
            evaluated = self.scanner.evaluate_token(launch)
            
            status = evaluated.get("status", "N/A")
            name = launch.get("name", "Unknown")[:20]
            market_cap = evaluated.get("market_cap", 0)
            liquidity = evaluated.get("liquidity", 0)
            holders = evaluated.get("holders", 0)
            volume = evaluated.get("volume", 0)
            mint = launch.get("mint", "unknown")[:10]
            
            tag = "snipe" if status == "SNIPE" else "watch" if status == "WATCH" else "alert"
            
            self.scanner_tree.insert(
                "", "end", text=str(evaluated.get("score", 0)),
                values=(status, name, f"${market_cap:,.0f}", f"${liquidity:,.0f}", holders, f"${volume:,.0f}", mint),
                tags=(tag,)
            )
    
    def refresh_balances(self):
        """Refresh balances manually"""
        threading.Thread(target=self._refresh_balances, daemon=True).start()
    
    def _refresh_balances(self):
        """Perform balance refresh"""
        self.balance_tracker.update_all_balances(self.wallet_manager.wallets)
        self.root.after(0, lambda: self.refresh_wallet_list())
        self.root.after(0, lambda: self.update_stats())
    
    def start_background_tasks(self):
        """Start periodic updates"""
        def background_update():
            while self.running:
                try:
                    self.balance_tracker.update_all_balances(self.wallet_manager.wallets)
                    self.root.after(0, lambda: self.update_stats())
                    time.sleep(CONFIG["REFRESH_INTERVAL"])
                except:
                    pass
        
        threading.Thread(target=background_update, daemon=True).start()
    
    def on_closing(self):
        """Handle window close"""
        self.running = False
        self.root.destroy()


# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    app = TradingBotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
