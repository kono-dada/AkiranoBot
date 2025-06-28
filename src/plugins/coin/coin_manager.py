import json
import os
from datetime import datetime, timedelta
from typing import Dict
from pydantic import BaseModel, Field, ValidationError
from .exceptions import CoinManagerException, InsufficientFundsException, TransferToSelfException


class UserAsset(BaseModel):
    coins: int = Field(ge=0)
    last_check_in: str | None = None  # ISO format date string, e.g., "2023-10-01T12:00:00"

class CoinManager:
    def __init__(
            self, 
            data_file: str = "data/coin/coin_data.json",
            daily_check_in_bonus: int = 500
        ):
        self.data_file = data_file
        self.data: Dict[str, UserAsset] = {}
        self.daily_check_in_bonus = daily_check_in_bonus
        self._load_data()

    def _load_data(self):
        if not os.path.exists(os.path.dirname(self.data_file)):
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                raw = json.load(f)
                for uid, v in raw.items():
                    try:
                        self.data[uid] = UserAsset(**v)
                    except ValidationError:
                        self.data[uid] = UserAsset(coins=0, last_check_in=None)
        else:
            # 文件不存在时自动创建空文件
            with open(self.data_file, "w") as f:
                json.dump({}, f)
            self.data = {}

    def _save_data(self):
        dir_path = os.path.dirname(self.data_file)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump({uid: asset.dict() for uid, asset in self.data.items()}, f, indent=4)

    def _ensure_user(self, user_id: str):
        if user_id not in self.data:
            self.data[user_id] = UserAsset(coins=0, last_check_in=None)
    
    def _ensure_valid_user_id(self, user_id: str):
        if not isinstance(user_id, str) or not user_id.isalnum() or len(user_id) > 64:
            raise ValueError("user_id must be an alphanumeric string up to 64 chars.")
        
    def _ensure_amount_positive(self, amount: int):
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive integer.")

    def get_balance(self, user_id: str) -> int:
        self._ensure_valid_user_id(user_id)
        self._ensure_user(user_id)
        return self.data[user_id].coins

    def modify_coins(self, user_id: str, amount: int) -> int:
        self._ensure_valid_user_id(user_id)
        self._ensure_user(user_id)
        if amount < 0 and self.data[user_id].coins + amount < 0:
            raise InsufficientFundsException("Insufficient funds: cannot have negative balance.")
        self.data[user_id].coins += amount
        self._save_data()
        return self.data[user_id].coins
    
    def fine(self, user_id: str, amount: int) -> int:
        self._ensure_valid_user_id(user_id)
        self._ensure_amount_positive(amount)
        self._ensure_user(user_id)
        if self.data[user_id].coins < amount:
            self.data[user_id].coins = 0  # 如果余额不足，设置为0
        self.data[user_id].coins -= amount
        self._save_data()
        return self.data[user_id].coins

    def daily_check_in(self, user_id: str) -> int:
        self._ensure_valid_user_id(user_id)
        self._ensure_user(user_id)
        last_check_in = self.data[user_id].last_check_in
        today = datetime.now().date()
        if last_check_in:
            last_check_in_date = datetime.fromisoformat(last_check_in).date()
            if last_check_in_date == today:
                raise CoinManagerException("User has already checked in today.")
        self.data[user_id].coins += self.daily_check_in_bonus  # Daily reward
        self.data[user_id].last_check_in = datetime.now().isoformat()
        self._save_data()
        return self.data[user_id].coins

    def transfer(self, from_user_id: str, to_user_id: str, amount: int) -> Dict[str, int]:
        self._ensure_valid_user_id(from_user_id)
        self._ensure_valid_user_id(to_user_id)
        self._ensure_amount_positive(amount)
        if from_user_id == to_user_id:
            raise TransferToSelfException("Cannot transfer coins to oneself.")
        self._ensure_user(from_user_id)
        self._ensure_user(to_user_id)
        if self.data[from_user_id].coins < amount:
            raise InsufficientFundsException("Insufficient funds for transfer.")
        self.data[from_user_id].coins -= amount
        self.data[to_user_id].coins += amount
        self._save_data()
        return {
            "from_user_balance": self.data[from_user_id].coins,
            "to_user_balance": self.data[to_user_id].coins
        }
    