# Script Python (2022) : connexion à MetaTrader 5 et export de la liste des symboles en CSV.
# Identifiants floutés : le compte de démonstration n'existe plus, mais un secret ne se publie pas.
import MetaTrader5 as mt
from tkinter import * 
import pandas as pd
import plotly.express as px
from datetime import datetime
#import DemoConnect, LiveConnect
import csv

#Connection compte demo

mt.shutdown()
mt.initialize()
login = ••••••••
password = "••••••••"
server = "AdmiralMarkets-Demo"

mt.login(login, password, server)

#data =["lol","lolo","lololo"]

#Acquisition des symbols

symbols=data =mt.symbols_get()
#Mise en place du .csv

data =[symbols]

tableau = open("essai.csv","w")
obj = csv.writer(tableau)
for element in data:
    obj.writerow(element)
tableau.close()


