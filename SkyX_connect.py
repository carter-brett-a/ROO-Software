# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 17:42:17 2019

@authors: 
Brett Carter, SPACE Research Centre, School of Science, RMIT University, brett.carter@rmit.edu.au
Erik Klein, IRAS Institute of Space Systems, Braunschweig, Germany, erik.klein@tu-bs.de
This code was developed as part of RMIT University's Robotic Optical Observatory (ROO) project.

"""

import win32com.client
import time

#TheSkyX Telescope
teleObj = win32com.client.Dispatch("TheSkyXAdaptor.RASCOMTele")

#TheSkyX main camera
camObj = win32com.client.Dispatch("CCDSoft2XAdaptor.ccdsoft5Camera")

#TheSkyX Object
theSkyObj = win32com.client.Dispatch("TheSkyXAdaptor.RASCOMTheSky")

#connect to mount
print("Connecting to mount")
teleObj.Connect()

#connect to main camera
print("Connecting to camera")
camObj.Connect()

#connect up the dome
print("Connecting to dome")
theSkyObj.ConnectDome()

#instruct mount to find home
print("Mount is finding home")
teleObj.FindHome()

#waiting for the mount to find home... usually takes a couple of minutes, so 5 should do the trick
time.sleep(95)

#turning tracking off (automatically goes to sidreal tracking after slew)
#Doing this because it could be a while before it's safe to open the dome...
teleObj.SetTracking(0,1,0,0)
#connect up autoguider...? Cannot see how to do this easily... maybe we'll revisit when we need it!!!

#then you're all done!!
