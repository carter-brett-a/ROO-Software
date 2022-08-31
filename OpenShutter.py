# -*- coding: utf-8 -*-
"""
Created on Thu May 16 17:13:03 2019

@authors: 
Brett Carter, SPACE Research Centre, School of Science, RMIT University, brett.carter@rmit.edu.au
This code was developed as part of RMIT University's Robotic Optical Observatory (ROO) project.

"""


import win32com.client
import csv
import sys
import os
import time

def unsafe_status_check(stat):
    
    csv_filename = 'C:/Users/RMIT/AppData/Local/VirtualStore/Program Files (x86)/AAG_CloudWatcher/CloudWatcher.csv'
    info = []
    
    #with open(csv_filename, newline='') as csvfile:
        
        #info = list(csv.reader(csvfile,delimiter = ','))
        
        #for line in info:
            
            #if "Unsafe" in line:
                #print("It's unsafe to open the dome! Halting program...")
                #print("Current dome status: ",stat)
                #print("( 0 = open, 1 = closed, 2 = opening, 3 - closing)")
                
                #sys.exit()
    with open(csv_filename, newline='') as csvfile:
        text = csv.reader(csvfile, delimiter=',', quotechar='"')
        
        row = list(text)
        
        first_row = row[0]
        second_row = row[1]
        
        safe_stat_key = first_row[16]
        
        if safe_stat_key != "Safe Status":
            print("Safe status isn't constant in weather message!! (you're assuming this... you need to fix it)")
            sys.exit()
        
        safe_status = second_row[16]
        
    while safe_status != "Safe":
        print("Unsafe weather conditions... waiting for improvement")
        print(time.ctime())
        time.sleep(60) #1 min
        
        with open(csv_filename, newline='') as csvfile:
        
            text2 = csv.reader(csvfile, delimiter=',', quotechar='"')

            row2 = list(text2)
        
            second_row = row2[1]            
            safe_status = second_row[16]
                
    
    print("Safe status detected!! Opening her up...")


#okay, this command only nudges the shutter open/closed... not fully open or fully close... need to learn how to do this... eventually...
command = "Shutter_1_Open"

#actual ASCOM dome object
domeObj = win32com.client.Dispatch("Ascom.ScopeDomeUSBDome.DomeLS")

domeObj.Connected = True

#Shutter status ( 0 = open, 1 = closed, 2 = opening, 3 - closing, from trial and error)
stat = domeObj.ShutterStatus

#First checking that it's safe to open the dome
unsafe_status_check(stat)

while stat != 0:
    domeObj.CommandString(command)
    stat = domeObj.ShutterStatus

print("Shutter opened")