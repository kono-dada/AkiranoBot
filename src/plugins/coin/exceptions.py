class CoinManagerException(Exception):
    pass

class InsufficientFundsException(CoinManagerException):
    pass

class TransferToSelfException(CoinManagerException):
    pass