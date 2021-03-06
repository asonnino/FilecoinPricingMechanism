#!/usr/bin/python3
from web3 import Web3
import argparse
from multi_dutch import Auction
import time


class Client:
    def __init__(self, account, provider, address, abi_file):
        self.w3 = Web3(Web3.IPCProvider(provider))
        with open(abi_file) as f:
            abi = f.read()
        self.contract = self.w3.eth.contract(address=address, abi=abi)
        self.w3.eth.defaultAccount = self.w3.eth.accounts[0]
        self.unlockAccount()


    def check_connection(self):
        return self.w3.isConnected()

    def listAccounts(self):
        for account in self.w3.eth.accounts:
            print(account, self.w3.eth.getBalance(account))


    def bid(self, size, duration, pice):   
        print("Submitting bid for", size, "GB of storage for", duration, "days")     
        transaction = self.contract.functions.submitBid(int(size), int(duration), int(price))
        tx_hash = transaction.transact()
        return self.w3.eth.waitForTransactionReceipt(tx_hash)

    def item(self, size, duration, price):
        print("Submitting item with", size, "GB of storage for", duration, "days", "and", price, "minimum price")
        transaction = self.contract.functions.addItem(int(size), int(duration), int(price))
        tx_hash = transaction.transact()
        return self.w3.eth.waitForTransactionReceipt(tx_hash)

    def unlockAccount(self):
        self.w3.geth.personal.unlockAccount(self.w3.eth.defaultAccount, 'password')

    def deployContract(self, abi_file, bin_file):
        with open(abi_file, 'r') as myfile:
            contract_abi = myfile.read()
            myfile.close()
        with open(bin_file, 'r') as myfile:
            contract_bin = myfile.read()
            myfile.close()

        #print("Accounts", self.listAccounts())
        contract = self.w3.eth.contract(abi=contract_abi, bytecode=contract_bin)
        tx_hash = contract.constructor().transact()
        tx_receipt = self.w3.eth.waitForTransactionReceipt(tx_hash)
        print("Contract deployed at", tx_receipt.contractAddress)
        return tx_receipt.contractAddress

    def solve_fake(self):
        bidsCounter = self.contract.functions.bidsCounter().call()
        bids = []
        for i in range(1, bidsCounter + 1):
            bids.append(self.contract.functions.bids(i).call())
        print("Fetched bids:", bids)

        itemsCounter = self.contract.functions.itemCounter().call()
        items = []
        for i in range(1, itemsCounter + 1):
            items.append(self.contract.functions.items(i).call())
        print("Fetched items:", items)

        bidderIDs = list(range(0, bidsCounter))
        itemIDs = list(range(0, itemsCounter))

        #valuation bidde -> item
        valuations = {}
        for bidder in bidderIDs:
            for item in itemIDs:
                ok = True
                #print("bidder", bidder, "item", item)
                for i in range(0, len(bids[bidder]) - 1):
                    #print("comparing features", bids[bidder][i], items[item][i])
                    if(bids[bidder][i] > items[item][i]):
                        valuations[bidder, item] = 0
                        ok = False
                        break
                if(ok):
                    valuations[bidder, item] = bids[bidder][2]
        
        list_min_prices = [v[2] for k,v in enumerate(items)]
        min_prices = {}
        for item in itemIDs:
            min_prices[item] = list_min_prices[item]
       

        auction = Auction(itemIDs, min_prices, bidderIDs, valuations)
        auction.solve()
        X, prices, score = auction.return_solution()

        X = [255 if x==None else x for x in X]
        
        transaction = self.contract.functions.submitSolution(X, prices, score+100)
        tx_hash = transaction.transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)

        print("Fake Solution submitted (score + 100)")

        
    def solve(self):
        bidsCounter = self.contract.functions.bidsCounter().call()
        bids = []
        for i in range(1, bidsCounter + 1):
            bids.append(self.contract.functions.bids(i).call())
        print("Fetched bids:", bids)

        itemsCounter = self.contract.functions.itemCounter().call()
        items = []
        for i in range(1, itemsCounter + 1):
            items.append(self.contract.functions.items(i).call())
        print("Fetched items:", items)

        if(len(bids) == 0 or len(items) == 0 ):
            print("Not enough items or bids present on the blockchain")
            return

        bidderIDs = list(range(0, bidsCounter))
        itemIDs = list(range(0, itemsCounter))

        #valuation bidde -> item
        valuations = {}
        for bidder in bidderIDs:
            for item in itemIDs:
                ok = True
                #print("bidder", bidder, "item", item)
                for i in range(0, len(bids[bidder]) - 1):
                    #print("comparing features", bids[bidder][i], items[item][i])
                    if(bids[bidder][i] > items[item][i]):
                        valuations[bidder, item] = 0
                        ok = False
                        break
                if(ok):
                    valuations[bidder, item] = bids[bidder][2]
        
        print("Derived valuations:", valuations)
        list_min_prices = [v[2] for k,v in enumerate(items)]
        min_prices = {}
        for item in itemIDs:
            min_prices[item] = list_min_prices[item]
       

        auction = Auction(itemIDs, min_prices, bidderIDs, valuations)
        print("Solving auction")
        #auction.print_assignments()
        auction.solve()
        X, prices, score = auction.return_solution()

        X = [255 if x==None else x for x in X]
        #print("X", X)
        #print("prices", prices)
        #print("score", score)
        auction.print_assignments()
        
        if(score == 0):
            print("No items assigned to bidders - skipping solution submission")
            return

        transaction = self.contract.functions.submitSolution(X, prices, score)
        tx_hash = transaction.transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)

        print("Solution submitted")


    def verify(self):
        X = []
        prices = []
        pricesSize = self.contract.functions.pricesCounter().call()
        XSize = self.contract.functions.XCounter().call()
        score = self.contract.functions.score().call()

        if(score == 0 or XSize == 0 or pricesSize == 0):
            print("No submitted solution yet")
            return
        for i in range(0, XSize):
            X.append(self.contract.functions.X(i).call())
        for i in range(0, pricesSize):
            prices.append(self.contract.functions.prices(i).call())
        X = [None if x==255 else x for x in X]

        bidsCounter = self.contract.functions.bidsCounter().call()
        bids = []
        for i in range(1, bidsCounter + 1):
            bids.append(self.contract.functions.bids(i).call())
        print("Fetched bids:", bids)

        itemsCounter = self.contract.functions.itemCounter().call()
        items = []
        for i in range(1, itemsCounter + 1):
            items.append(self.contract.functions.items(i).call())
        print("Fetched items:", items)

        bidderIDs = list(range(0, bidsCounter))
        itemIDs = list(range(0, itemsCounter))

        #valuation bidde -> item
        valuations = {}
        for bidder in bidderIDs:
            for item in itemIDs:
                ok = True
                #print("bidder", bidder, "item", item)
                for i in range(0, len(bids[bidder]) - 1):
                    #print("comparing features", bids[bidder][i], items[item][i])
                    if(bids[bidder][i] > items[item][i]):
                        valuations[bidder, item] = 0
                        ok = False
                        break
                if(ok):
                    valuations[bidder, item] = bids[bidder][2]
                else:
                    valuations[bidder, item] = 0
        list_min_prices = [v[2] for k,v in enumerate(items)]
        min_prices = {}
        for item in itemIDs:
            min_prices[item] = list_min_prices[item]
       
        #print("itemIDs", itemIDs)
        #print("bidderIDs", itemIDs)
        #print("min_prices", min_prices)
        #print("valuations", valuations)
        #print("prices", prices)
        #print("score", score)
        auction = Auction(itemIDs, min_prices, bidderIDs, valuations)
        auction.set_solution(X, prices, score)
        auction.print_assignments()
        if(auction.verify() == False):
            print("Solution is incorrect")
            answer = input("Would you like to submit a proof of misbehaviour?[y/n]:")
            if(answer == 'y'):
                transaction = self.contract.functions.wrongScore()
                tx_hash = transaction.transact()
                self.w3.eth.waitForTransactionReceipt(tx_hash)
                print("Proof of misbehaviour submitted")
                print("The incorrect solution will be removed and its creator penalized")
        else:
            print("Assignment verified correctly")


                
                



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FilecoinPricingMechanism Client.')
    # Used for bid submittion
    parser.add_argument('--addr', default='', help='Contract address')
    parser.add_argument("command", choices=['verify', 'item', 'list', 'deploy', 'bid', 'solve', 'solve-fake'], help="Command to execute")
    parser.add_argument('--account', help='Self account', required=False)
    parser.add_argument(
        '--provider', default='../data/geth.ipc', help='ethereum IPC provider URL')
    parser.add_argument(
        '--abi', default='../contract/asterisk.abi', help='Contract ABI file')
    parser.add_argument(
        '--bin', default='../contract/asterisk.bin', help='Contract BIN file')
    parser.add_argument(
        '--size', help='Storage size')
    parser.add_argument(
        '--duration', help='Storage duration')
    parser.add_argument(
        '--price', help='Price')
    args = parser.parse_args()


    client = Client(args.account, args.provider, args.addr, args.abi)

    
    if(args.command == 'bid'):
        if(args.size == None):
            size = input("How much storage do you need?[GB]:")
        else:
            size = args.size
        if(args.duration == None):
            duration = input("What's the length of the lease?[days]:")
        else:
            duration = args.duration
        if(args.price == None):
            price = input("How much are you willing to pay?[ETH]:")
        else:
            price = args.price
        result = client.bid(size, duration, price)
        print("Your bid was submitted.")
    elif(args.command == 'item'):
        if(args.size == None):
            size = input("How much storage do you offer?[GB]:")
        else:
            size = args.size
        if(args.duration == None):
            duration = input("What's the length of the offered lease?[days]:")
        else:
            duration = args.duration
        if(args.price == None):
            price = input("What's the minimum price for this storage?[ETH]:")
        else:
            price = args.price
        result = client.item(size, duration, price)
        print("Your item was submitted.")
    elif(args.command == 'deploy'):
        client.deployContract(args.abi, args.bin)
    elif(args.command == 'list'):
        client.listAccounts()
    elif(args.command == 'solve'):
        client.solve()
    elif(args.command == 'verify'):
        client.verify()
    elif(args.command == 'solve-fake'):
        client.solve_fake()
    else:
        print(command, "is not yet implemented")
        quit()
