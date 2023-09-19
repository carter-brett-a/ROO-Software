# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 17:42:17 2019

@authors: 
Brett Carter, SPACE Research Centre, School of Science, RMIT University, brett.carter@rmit.edu.au
Erik Klein, IRAS Institute of Space Systems, Braunschweig, Germany, erik.klein@tu-bs.de
This code was developed as part of RMIT University's Robotic Optical Observatory (ROO) project.

"""

import win32com.client

#TheSkyX Telescope
teleObj = win32com.client.Dispatch("TheSky64.sky6RASCOMTele")
teleObj.Connect()

#TheSkyX main camera
camObj = win32com.client.Dispatch("TheSky64.ccdsoftCamera")
camObj.Connect()

#TheSkyX Object
theSkyObj = win32com.client.Dispatch("TheSky64.sky6RASCOMTheSky")

#dome object
domeObj = win32com.client.Dispatch("Ascom.ScopeDomeUSBDome.DomeLS")
domeObj.Connected = True


#park telescope
print("Parking telescope and then switching it off")
teleObj.Park()


#disconnect the main camera
print("Disconnecting camera")
camObj.Disconnect()

#park dome (manually selected here to match what we've told ScopeDomeLS)
print("Parking dome")
domeObj.SlewToAzimuth(78)

#disconnect up the dome
print("Disconnecting dome")
theSkyObj.DisconnectDome()

#exits TheSkyX
print("Exiting TheSkyX")
theSkyObj.quit()
