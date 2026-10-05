#!/usr/bin/env python3
"""
Solana/Polygon/Base/PumpFun Trading & Sniping Bot
Single executable script with balance counters, address generation, and donation link
"""

import os
import sys
import json
import time
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import threading
import queue

# Web3 & Blockchain imports
try:
    from solders.keypair import Keypair
    from solders.pubkey import PublicKey
    from solders.rpc.responses import GetAccountInfoResp
    from solana.rpc.api import Client as SolanaClient
    from solana.exceptions import SolanaRpcException
except ImportError:
    print("Installing Solana dependencies...")
    os.system("pip install solders solana")
    from solders.keypair import Keypair
    from solders.pubkey import PublicKey
    from solders.rpc.responses import GetAccountInfoResp
    from solana.rpc.api import Client as SolanaClient
    from solana.exceptions import SolanaRpcException

try:
    from web3 import Web3
except ImportError:
    print("Installing Web3 dependencies...")
    os.system("pip install web3")
    from web3 import Web3

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests")
    import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "DONATION_LINK": "https://cash.app/$Chronorub",
    "SOLANA_RPC": "https://api.mainnet-beta.solana.com",
    "POLYGON_RPC": "https://polygon-rpc.com",
    "BASE_RPC": "https://mainnet.base.org",
    "PUMPFUN_API": "https://frontend-api.pump.fun",
    "REFRESH_RATE": 2,  # seconds
    "MAX_WALLETS": 10,
}

# ============================================================================
# WALLET MANAGER
# ============================================================================

class WalletManager:
    """Generate and manage wallet addresses across chains"""
    
    def __init__(self):
        self.wallets: Dict[str, Dict] = {}
        self.wallet_file = "wallets.json"
        self.load_wallets()
    
    def generate_solana_wallet(self) -> Dict:
        """Generate a new Solana keypair"""
        keypair = Keypair()
        return {
            "chain": "solana",
            "address": str(keypair.pubkey()),
            "private_key": keypair.secret().hex(),
            "created": datetime.now().isoformat()
        }
    
    def generate_evm_wallet(self) -> Dict:
        """Generate a new EVM-compatible wallet (Polygon/Base)"""
        w3 = Web3()
        account = w3.eth.account.create()
        return {
            "chain": "evm",
            "address": account.address,
            "private_key": account._private_key.hex(),
            "created": datetime.now().isoformat()
        }
    
    def generate_new_wallet(self, chain: str = "solana") -> Dict:
        """Generate wallet for specified chain"""
        if chain.lower() == "solana":
            wallet = self.generate_solana_wallet()
        elif chain.lower() in ["polygon", "base", "evm"]:
            wallet = self.generate_evm_wallet()
        else:
            raise ValueError(f"Unsupported chain: {chain}")
        
        wallet_id = f"{chain}_{len(self.wallets)}"
        self.wallets[wallet_id] = wallet
        self.save_wallets()
        return wallet
    
    def save_wallets(self):
        """Persist wallets to file"""
        with open(self.wallet_file, "w") as f:
            json.dump(self.wallets, f, indent=2)
    
    def load_wallets(self):
        """Load wallets from file if exists"""
        if os.path.exists(self.wallet_file):
            with open(self.wallet_file, "r") as f:
                self.wallets = json.load(f)
    
    def get_all_wallets(self) -> List[Dict]:
        """Return all stored wallets"""
        return list(self.wallets.values())


# ============================================================================
# BALANCE TRACKER
# ============================================================================

class BalanceTracker:
    """Track balances across multiple chains"""
    
    def __init__(self):
        self.solana_client = SolanaClient(CONFIG["SOLANA_RPC"])
        self.polygon_w3 = Web3(Web3.HTTPProvider(CONFIG["POLYGON_RPC"]))
        self.base_w3 = Web3(Web3.HTTPProvider(CONFIG["BASE_RPC"]))
        self.balances: Dict[str, Dict] = {}
    
    def get_solana_balance(self, address: str) -> Optional[float]:
        """Get SOL balance for Solana address"""
        try:
            pubkey = PublicKey(address)
            response = self.solana_client.get_balance(pubkey)
            lamports = response.value
            sol = lamports / 1e9
            return sol
        except Exception as e:
            print(f"[ERROR] Solana balance check failed for {address}: {e}")
            return None
    
    def get_polygon_balance(self, address: str) -> Optional[float]:
        """Get MATIC balance for Polygon address"""
        try:
            balance_wei = self.polygon_w3.eth.get_balance(address)
            balance_matic = self.polygon_w3.from_wei(balance_wei, 'ether')
            return float(balance_matic)
        except Exception as e:
            print(f"[ERROR] Polygon balance check failed for {address}: {e}")
            return None
    
    def get_base_balance(self, address: str) -> Optional[float]:
        """Get ETH balance for Base address"""
        try:
            balance_wei = self.base_w3.eth.get_balance(address)
            balance_eth = self.base_w3.from_wei(balance_wei, 'ether')
            return float(balance_eth)
        except Exception as e:
            print(f"[ERROR] Base balance check failed for {address}: {e}")
            return None
    
    def update_balances(self, wallets: List[Dict]):
        """Update balances for all wallets"""
        for wallet in wallets:
            wallet_id = f"{wallet['chain']}_0"
            
            if wallet['chain'] == 'solana':
                balance = self.get_solana_balance(wallet['address'])
                self.balances[wallet['address']] = {
                    'chain': 'Solana',
                    'symbol': 'SOL',
                    'balance': balance if balance else 0,
                    'updated': datetime.now().isoformat()
                }
            elif wallet['chain'] == 'evm':
                poly_bal = self.get_polygon_balance(wallet['address'])
                base_bal = self.get_base_balance(wallet['address'])
                self.balances[f"{wallet['address']}_polygon"] = {
                    'chain': 'Polygon',
                    'symbol': 'MATIC',
                    'balance': poly_bal if poly_bal else 0,
                    'updated': datetime.now().isoformat()
                }
                self.balances[f"{wallet['address']}_base"] = {
                    'chain': 'Base',
                    'symbol': 'ETH',
                    'balance': base_bal if base_bal else 0,
                    'updated': datetime.now().isoformat()
                }


# ============================================================================
# PUMPFUN SNIPER
# ============================================================================

class PumpFunSniper:
    """Monitor and snipe PumpFun launches"""
    
    def __init__(self):
        self.api_url = CONFIG["PUMPFUN_API"]
        self.watched_tokens: List[Dict] = []
    
    def get_latest_launches(self, limit: int = 10) -> List[Dict]:
        """Fetch latest token launches from PumpFun"""
        try:
            response = requests.get(
                f"{self.api_url}/api/public/all?sort=created&limit={limit}",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch PumpFun launches: {e}")
        return []
    
    def check_token_details(self, mint: str) -> Optional[Dict]:
        """Get detailed token info"""
        try:
            response = requests.get(
                f"{self.api_url}/api/public/coin/{mint}",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch token details: {e}")
        return None
    
    def evaluate_snipe(self, token: Dict) -> bool:
        """Evaluate if token meets snipe criteria"""
        try:
            # Basic heuristics
            market_cap = float(token.get('marketCap', 0))
            liquidity = float(token.get('liquidity', 0))
            holders = int(token.get('holders', 0))
            
            # Criteria: low market cap, decent liquidity, growing holders
            if market_cap < 50000 and liquidity > 100 and holders > 5:
                return True
        except:
            pass
        return False


# ============================================================================
# UI & DISPLAY
# ============================================================================

class TradingBotUI:
    """Terminal UI for the trading bot"""
    
    def __init__(self, wallet_manager: WalletManager, balance_tracker: BalanceTracker, sniper: PumpFunSniper):
        self.wallet_manager = wallet_manager
        self.balance_tracker = balance_tracker
        self.sniper = sniper
    
    def clear_screen(self):
        """Clear terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print bot header"""
        print("\n" + "="*80)
        print(" "*15 + "⚡ SOLANA/POLYGON/BASE/PUMPFUN TRADING BOT ⚡")
        print("="*80)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bot running...\n")
    
    def print_wallets(self):
        """Display all wallets"""
        wallets = self.wallet_manager.get_all_wallets()
        if not wallets:
            print("📭 No wallets created yet. Type 'new' to generate one.\n")
            return
        
        print("💼 WALLETS & BALANCES")
        print("-" * 80)
        for wallet in wallets:
            chain = wallet['chain'].upper()
            address = wallet['address'][:10] + "..." + wallet['address'][-8:]
            
            # Get balance if exists
            balance_key = list(wallet['address'] if k.startswith(wallet['address']) for k in self.balance_tracker.balances.keys() or [wallet['address']])
            balance_info = self.balance_tracker.balances.get(wallet['address'], {})
            balance = balance_info.get('balance', 0)
            symbol = balance_info.get('symbol', 'N/A')
            
            print(f"  [{chain}] {address} | Balance: {balance:.6f} {symbol}")
        print()
    
    def print_pumpfun_launches(self):
        """Display latest PumpFun launches"""
        launches = self.sniper.get_latest_launches(5)
        if not launches:
            print("📢 No PumpFun launches found.\n")
            return
        
        print("🚀 LATEST PUMPFUN LAUNCHES")
        print("-" * 80)
        for token in launches[:5]:
            name = token.get('name', 'Unknown')
            mint = token.get('mint', 'N/A')[:10] + "..."
            market_cap = float(token.get('marketCap', 0)) / 1000
            liquidity = float(token.get('liquidity', 0))
            
            snipe_worthy = "✅ SNIPE!" if self.sniper.evaluate_snipe(token) else "⏸️"
            print(f"  {snipe_worthy} {name} | Market Cap: ${market_cap:.2f}K | Liquidity: ${liquidity:.2f}")
        print()
    
    def print_commands(self):
        """Display available commands"""
        print("📋 COMMANDS:")
        print("  new sol      - Generate new Solana wallet")
        print("  new eth      - Generate new EVM wallet (Polygon/Base)")
        print("  balances     - Refresh all balances")
        print("  pumpfun      - Check PumpFun launches")
        print("  watch        - Monitor tokens for snipes")
        print("  export       - Export wallets (JSON)")
        print("  clear        - Clear screen")
        print("  exit/quit    - Exit bot")
        print("\n💰 Donation: " + CONFIG["DONATION_LINK"])
        print("="*80 + "\n")
    
    def run(self):
        """Main loop"""
        try:
            while True:
                self.clear_screen()
                self.print_header()
                self.print_wallets()
                self.print_pumpfun_launches()
                self.print_commands()
                
                user_input = input("➜ Enter command: ").strip().lower()
                
                if user_input == "new sol":
                    wallet = self.wallet_manager.generate_new_wallet("solana")
                    print(f"\n✅ New Solana wallet created!\n  Address: {wallet['address']}\n")
                    input("Press Enter to continue...")
                
                elif user_input == "new eth":
                    wallet = self.wallet_manager.generate_new_wallet("evm")
                    print(f"\n✅ New EVM wallet created!\n  Address: {wallet['address']}\n")
                    input("Press Enter to continue...")
                
                elif user_input == "balances":
                    print("\n🔄 Refreshing balances...")
                    self.balance_tracker.update_balances(self.wallet_manager.get_all_wallets())
                    time.sleep(1)
                    print("✅ Balances updated!\n")
                    input("Press Enter to continue...")
                
                elif user_input == "pumpfun":
                    print("\n🔍 Fetching PumpFun launches...\n")
                    launches = self.sniper.get_latest_launches(10)
                    for token in launches:
                        if self.sniper.evaluate_snipe(token):
                            print(f"🎯 SNIPE OPPORTUNITY: {token.get('name')} - {token.get('mint')[:10]}...")
                    input("\nPress Enter to continue...")
                
                elif user_input == "watch":
                    print("\n👀 Watching for snipe opportunities (30 seconds)...")
                    for i in range(6):
                        launches = self.sniper.get_latest_launches(5)
                        for token in launches:
                            if self.sniper.evaluate_snipe(token):
                                print(f"  [SNIPE] {token.get('name')} at {datetime.now().strftime('%H:%M:%S')}")
                        time.sleep(5)
                    input("\nPress Enter to continue...")
                
                elif user_input == "export":
                    filename = f"wallets_export_{int(time.time())}.json"
                    with open(filename, 'w') as f:
                        json.dump(self.wallet_manager.wallets, f, indent=2)
                    print(f"\n✅ Wallets exported to {filename}\n")
                    input("Press Enter to continue...")
                
                elif user_input == "clear":
                    continue
                
                elif user_input in ["exit", "quit"]:
                    print("\n👋 Thanks for using the Trading Bot! Donate: " + CONFIG["DONATION_LINK"])
                    sys.exit(0)
                
                else:
                    print("\n❌ Unknown command. Try again.\n")
                    input("Press Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped. Donate: " + CONFIG["DONATION_LINK"])
            sys.exit(0)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point"""
    print("🚀 Initializing Trading Bot...")
    
    wallet_manager = WalletManager()
    balance_tracker = BalanceTracker()
    sniper = PumpFunSniper()
    
    ui = TradingBotUI(wallet_manager, balance_tracker, sniper)
    ui.run()


if __name__ == "__main__":
    main()
