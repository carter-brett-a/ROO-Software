# -*- coding: utf-8 -*-
"""
Created on Tue Sep 26 20:55:14 2023

"""

# -*- coding: utf-8 -*-
"""
Created on Tue Feb  9 13:56:05 2021

@author: Dr Brett Carter and Maggie Williams, RMIT University, as part of Maggie's work experience with RMIT and Saber Astronautics, and Sai Vallapureddy as part of his PhD works

Calculations on the viewing elevation and azimuth for a given location based on formulas in Curtis 2020 "Orbital Mechanics for Engineering Students"

Purpose: To slew the ROO telescope through a search grid around the GEO belt location. 
It calculates the location of the GEO belt in azimuth and elevation for a given location, and then slews across those azimuths and elevations, but also sweeping in elevation 
to capture the wider GEO region (e.g., searching for non-zero inclinations). 

This version of the code has also been developed to automatically upload JSON data up to the UDL (Sai helped with this). The code also has a "pause until safe" routine that's triggered by a 
closed/closing shutter... it also checks for power issues...

This version also includes the added capability of pausing and resuming the GEO search using JSON files (Kaifur Rashed helped with this).

This is the primary operational code for the SACT exercise, and is actually our first intended routine GEO monitoring code for the daily operations of ROO (eventually)


"""


import numpy as np
import time
import math
import matplotlib.pyplot as plt
import sys
import win32com.client
import runpy
import csv
import os
import datetime
import threading

from astropy.visualization import astropy_mpl_style
plt.style.use(astropy_mpl_style)

from astropy.io import fits
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from astropy.stats import gaussian_fwhm_to_sigma
from astropy import units as u
from astropy.convolution import Gaussian2DKernel
from photutils.background import Background2D,MedianBackground
from photutils.segmentation import detect_sources,deblend_sources
from photutils.segmentation import SourceCatalog
from astropy.time import Time, TimeDelta
from astropy.wcs import WCS

from pywintypes import com_error

from astropy.table import QTable, Table, Column, unique

import pandas as pd
import json
import requests
import base64
from cryptography.fernet import Fernet
from io import StringIO


floor = math.floor
sqrt = math.sqrt
sin = math.sin
cos = math.cos
pi = math.pi
asin = math.asin
acos = math.acos
 
# Specify the folder path for JSON files
folder_path = "C:\Telescope_Data\OneDrive - RMIT University\Science\Telescope\Data_subset\JSON"
teleobj = win32com.client.Dispatch("TheSky64.sky6RASCOMTele")
domeObj = win32com.client.Dispatch("Ascom.ScopeDomeUSBDome.DomeLS") 
 
# Initialize a list for scheduled observations
scheduled_observations = []
def process_json_files_thread(folder_path, scheduled_observations):
    while True:
        files = os.listdir(folder_path)
        current_time = datetime.datetime.now()

        for file_name in files:
            if file_name.lower().endswith('.json') and 'observation' in file_name.lower():
                json_file_path = os.path.join(folder_path, file_name)

                with open(json_file_path, 'r') as json_file:
                    data = json.load(json_file)
                    target_ra = data['ra']
                    target_dec = float(data['dec'])
                    target_time = data['time']
                    exposure_time = float(data['exposure time'])
                    #print(target_ra)
                    #print(type(target_ra))
                    if target_ra is not None and target_dec is not None and target_time is not None:
                        target_datetime = datetime.datetime.strptime(target_time, '%Y-%m-%dT%H:%M:%S')

                        # Calculate the slewing time 5 minutes before the specified time
                        slewing_time = target_datetime - datetime.timedelta(minutes=5)

                        # Check if it's time to add the observation to the scheduled list
                        if current_time < slewing_time:
                            # Add the observation to the scheduled list
                            if len(scheduled_observations) == 0:
                                scheduled_observations.append((target_datetime, target_ra, target_dec, exposure_time, file_name))
                            else:
                                #this little section isn't working properly... 
                                #I reckon it's the if statement.. it's just endlessly appending once a second observation JSON file gets added
                                if scheduled_observations[len(scheduled_observations) - 1][0] != target_datetime: #Attempt to stop same observation being appended
                                    scheduled_observations.append((target_datetime, target_ra, target_dec, exposure_time, file_name))
                                    print(f"Scheduled observation for RA: {target_ra}, Dec: {target_dec} at {target_datetime}")
                        #else:
                            #print(f"Ignoring observation with time in the past: {target_time}")

        # Sleep for 5 minutes before checking again
        #time.sleep(300)  # Check every 5 minutes 
def check_shutter_status_and_record_observation(teleobj, domeObj, camObj, observation, folder_path):
    current_time = datetime.datetime.now()
    target_datetime, target_ra, target_dec, exposure_time, file_name = observation
    
    # Calculate slewing time 5 minutes before the specified time
    slewing_time = target_datetime - datetime.timedelta(minutes=5)
    # Doing a shutter status check
    # Shutter status (0 = open, 1 = closed, 2 = opening, 3 = closing, from trial and error)
    stat = domeObj.ShutterStatus

    if stat != 0:
        # Record the observation as "Image not captured due to unsafe shutter status"
        observation_data = {
            "status": "unsafe_shutter",
            "target_ra": target_ra,
            "target_dec": target_dec,
            "observation_time": current_time.strftime('%Y-%m-%dT%H:%M:%S')
        }

        observation_file_path = os.path.join(folder_path, f"unsafe_shutter_{file_name}")
        with open(observation_file_path, 'w') as observation_file:
            json.dump(observation_data, observation_file, indent=4)

        print("Observation saved as unsafe due to shutter status.")
    else:
        # Wait for the specified time to slew - commented out as slewing time check already undertaken by the other subroutine
        #while datetime.datetime.now() <= slewing_time:
            #pass
        # Slew to the specified location
        print(f"Slewing to RA: {target_ra}, Dec: {target_dec} at {slewing_time}")
        teleobj.SlewToRaDec(target_ra, target_dec, 'Ra_%d_Dec_%d' % (target_ra, target_dec))
        while teleobj.IsSlewComplete != 1:
            pass
        print("Telescope is in position.")
            
        # Wait for the specified time to capture an image
        while datetime.datetime.now() < target_datetime:
            pass

        # Check if the exposure time exceeds the maximum allowed (5 seconds) - 
        #Throwing error at the moment, recongizes exposure_time as string - I reckon I fixed it... we were sending this the file name
        if exposure_time <= 5.0:
            # Set the camera exposure time
            camObj.ExposureTime = exposure_time
            # Capture 5 images and save them to the specified image folder
            for i in range(5):
                # Capture an image
                print(f"Capturing image {i + 1} with exposure time {exposure_time} seconds...")
                camObj.TakeImage()

                # Record the observation as "Image captured"
                observation_data = {
                    "status": "image_captured",
                    "target_ra": target_ra,
                    "target_dec": target_dec,
                    "observation_time": current_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    "exposure_time": exposure_time
                }

                observation_file_path = os.path.join(folder_path, f"image_captured_{file_name}_image_{i}.json")
                with open(observation_file_path, 'w') as observation_file:
                    json.dump(observation_data, observation_file, indent=4)

                print(f"Image {i + 1} captured and saved.")
        else:
            # Exposure time exceeds the maximum allowed, record as "Exposure time exceeded"
            observation_data = {
                "status": "exposure_time_exceeded",
                "target_ra": target_ra,
                "target_dec": target_dec,
                "observation_time": current_time.strftime('%Y-%m-%dT%H:%M:%S'),
                "exposure_time": exposure_time
            }

            observation_file_path = os.path.join(folder_path, f"exposure_time_exceeded_{file_name}")
            with open(observation_file_path, 'w') as observation_file:
                json.dump(observation_data, observation_file, indent=4)

            print(f"Exposure time {exposure_time} seconds exceeded.")
json_files_thread = threading.Thread(target=process_json_files_thread, args=(folder_path, scheduled_observations))
json_files_thread.start()

# Create a function to perform scheduled observations
def perform_scheduled_observations(teleobj, domeObj, scheduled_observations, folder_path):
    #while True:
    current_time = datetime.datetime.now()
       
    for observation in scheduled_observations:
        target_datetime, target_ra, target_dec, exposure_time, file_name = observation
        slewing_time = target_datetime - datetime.timedelta(minutes=5)

        if current_time >= slewing_time:
            print(f"Executing observation for RA: {target_ra}, Dec: {target_dec} at {current_time}")

                # Check and record observations when the shutter is closed
            check_shutter_status_and_record_observation(
                teleobj, domeObj, camObj, observation, folder_path
            )

                # Remove the executed observation from the list
            scheduled_observations.remove(observation)

        # Sleep for a while before checking again (adjust the sleep interval as needed)
        #time.sleep(30)  # Check every minute
    # Sleep for a while before checking again (adjust the sleep interval as needed)
    #time.sleep(30)  # Check every 30 seconds
# Start the function to perform scheduled observations in the background
#perform_scheduled_observations(teleobj, domeObj, scheduled_observations, folder_path)
 
def satellite_detect(image_dir, filename, png_key, csv_key):
      
    
    #maximum eccentricity for ellipse around source to be considered a possible satellite
    max_ecc = 0.75

    #minimum orientation difference (from the mean across the image) in order to be considered a possible satellite
    orient_diff_min = 10 * u.deg

    
    #first checking that directories exist for PNG and CSV files that we'll produce (if the keys are set)
    if png_key == True:
        saved_pngs_dir = image_dir+'/'+'PNGs'
        if os.path.isdir(saved_pngs_dir) == False:
            os.makedirs(saved_pngs_dir)
    
    if csv_key == True:
        saved_csvs = image_dir+'/'+'CSVs'
        if os.path.isdir(saved_csvs) == False:
            os.makedirs(saved_csvs)
    
    image_file = filename
    
    #just extracting the filename without the path for use in the CSV and PNG naming later on...
    fit_name = os.path.basename(image_file)
    
    data1 = fits.getdata(image_file)
    data = np.float64(data1)
    
    #for the issue of sources being identified on the edges of the images
    dims = data.shape
    dpix = 20   #width of mask on each axis in # of pixels
    #x-axis mask
    xmin_window = 0 + dpix
    xmax_window = dims[1] - dpix
    #y-axis mask
    ymin_window = 0 + dpix
    ymax_window = dims[0] - dpix

    #sys.exit()

    #----------------------------------------------
    #this threshold technique appears to be rather slow...
    #from photutils.segmentation import detect_threshold
    #threshold = detect_threshold(data, nsigma=2.)

    
    bkg_estimator = MedianBackground()
    bkg = Background2D(data, (50, 50), filter_size=(3, 3),
                       bkg_estimator=bkg_estimator)
    data -= bkg.background  # subtract the background
    threshold = 3. * bkg.background_rms  # above the background

    
    sigma = 3.0 * gaussian_fwhm_to_sigma  # FWHM = 3.
    kernel = Gaussian2DKernel(sigma, x_size=3, y_size=3)
    kernel.normalize()
    #kernel.normalize()
    #npixels = 25
    npixels = 15
        
    sats_in_image = 0.
    
    xpos = []
    ypos = []
    
    
    #segm = detect_sources(data, threshold, npixels=25, kernel=kernel)
    segm = detect_sources(data, threshold, npixels=15)
        
    if segm is None:
        print("No sources found... bad image")
            
    if segm is not None:
        print("Deplending now.")
            
        segm_deblend = deblend_sources(data, segm, npixels, labels=None, nlevels=32, contrast=0.001)

                
        print("Deplending complete.")
                
                
        norm = ImageNormalize(stretch=SqrtStretch())
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(35, 25))
        ax1.imshow(data, origin='lower', cmap='Greys_r', norm=norm);
        ax1.set_title('Data');
        cmap = segm.make_cmap(seed=123)
        ax2.imshow(segm, origin='lower', cmap=cmap, interpolation='nearest');
        ax2.set_title('Segmentation Image');
                
                
        cat = SourceCatalog(data, segm_deblend)
        
        if csv_key == True:
            tbl = cat.to_table()
            #writing table to csv file for further analysis...
            #tbl.write(saved_csvs+image_file+".csv",format = "ascii.csv",overwrite=True)
            tbl.write(saved_csvs+"/"+fit_name+".csv",format = "ascii.csv",overwrite=True)
                
            
            
        #cat_size = sys.getsizeof(cat)
                
        #mean_orient = np.mean(cat.orientation)
        mean_orient = np.median(cat.orientation)
            
        for i, element in enumerate(cat):
            aperture = cat.kron_aperture[i]
            ecc = cat.eccentricity[i]
            orient_diff = abs(cat.orientation[i]-mean_orient)
                    
                    
            #I had to insert this line because some of the apertures were being spat out as "Nonetype"... 
            #I'm assuming because the image quality??? But, images cleaned using AstroImageJ didn't work...
            #if aperture is not None and (ecc < max_ecc or orient_diff > orient_diff_min):
            #if aperture is not None and (ecc < max_ecc or orient_diff > orient_diff_min) and (aperture.positions[0] > xmin_window and aperture.positions[0] < xmax_window) and (aperture.positions[1] > ymin_window and aperture.positions[1] < ymax_window):
            if aperture is not None and (ecc < max_ecc or orient_diff > orient_diff_min) and (aperture.positions[0] > xmin_window and aperture.positions[0] < xmax_window) and (aperture.positions[1] > ymin_window and aperture.positions[1] < ymax_window):
                    
                #aperture.plot(axes=ax1, color='white', lw=1.5)
                aperture.plot(axes=ax2, color='white', lw=1.5)
                            
                xpos.append(aperture.positions[0])
                ypos.append(aperture.positions[1])
                            
                ax2.plot(aperture.positions[0],aperture.positions[1],color = 'red', marker = 'o', markersize = 22, mfc='none');
                print("Possible satellite found")
                    
                sats_in_image += 1
        
                    
        plt.ioff()
        if png_key == True:
            fig.savefig(saved_pngs_dir+"/"+fit_name+".png");
        plt.close("all")
                            
        data = []
        data1 = []
        segm = []
        segm_deblend = []
    
    
    if sats_in_image == 0:
        return(False,None,None) 
    else:
        return(True, xpos, ypos)





def zero_to_360(x):
    
    floor = math.floor
    
    if x >= 360:
        x = x - (floor(x/360)*360)
    
    if x < 0:
        x = x - ((floor(x/360)-1)*360)
    
    return(x)





def r_to_azi_elev(r_sat,obs):

    #First, find the position vector of the observer - for this we need to calculate the Local Sidereal Time
    current_time=time.gmtime()

    year=current_time.tm_year
    month=current_time.tm_mon
    day=current_time.tm_mday
    
    hour=current_time.tm_hour
    mins=current_time.tm_min
    secs=current_time.tm_sec

    long = obs[1]

    #Calculating the local sidereal time
    theta = sidereal_lt(year,month,day,hour,mins,secs,long)

    #For testing!! Remove after testing!
    #theta = 110

    #sidereal local time
    theta = theta*pi/180
    #latitude
    phi = obs[0]*pi/180

    #Now that we have the local sidereal time... we can calculate the position vector of the observer...
    Re = 6378
    H = obs[2]
    f = 0.003353    #Oblateness factor for Earth

    #Equation 5.56 (accounting for Earth's oblateness)
    coeff1 = (Re / (sqrt(1 - (2*f - f**2) * (sin(phi))**2))) + H
    coeff2 = ((Re * (1 - f)**2)/ (sqrt(1 - (2*f - f**2) * (sin(phi))**2))) + H
    
    Rx_obs = coeff1 * cos(phi) * cos(theta)
    Ry_obs = coeff1 * cos(phi) * sin(theta)
    Rz_obs = coeff2 * sin(phi)

    #The position vector of the observer
    R_obs = [Rx_obs, Ry_obs, Rz_obs]


    #The position vector of the satellite relative to the observer
    a=np.array(r_sat)
    b=np.array(R_obs)
    rho = a - b

    rho = np.transpose(rho)

    #############################################################################
    #############################################################################
    #Need to quickly calculate the longitude of the satellite (for later sorting) 
    #taking the angle between the satellite position vector in the x-y plane and the x axis
    x_axis = np.array([1000,0])
    r_sat_xy = a[0:2]
    
    r_sat_mag = np.linalg.norm(r_sat_xy)
    x_axis_mag = np.linalg.norm(x_axis)
    
    dot_xy = np.dot(r_sat_xy,x_axis)
    
    #if r_sat_xy[1] >= 0:
    theta_sat =  acos(dot_xy/(r_sat_mag*x_axis_mag))
        
    theta_sat *= 180./pi
    
    #being careful to check quandrant
    if r_sat_xy[1] < 0:
        
        theta_sat = 360. - theta_sat
    
    theta_sat = zero_to_360(theta_sat)
    
    #print(theta_sat)
    
    sat_long = sidereal_long(year,month,day,hour,mins,secs,theta_sat)
    #############################################################################
    #############################################################################


    #Now we need to transform rho from geocentric coords into topocentric coords, using equation 5.62a
    Qx = np.array([-sin(theta), cos(theta), 0])
    Qy = np.array([-sin(phi)*cos(theta), -sin(phi)*sin(theta), cos(phi)])
    Qz = np.array([cos(phi)*cos(theta), cos(phi)*sin(theta), sin(phi)])

    #The transform matrix - geocentric to topocentric (the other way around is simply the transpose of this matrix... which is pretty neat!!)
    Q = np.array([Qx, Qy, Qz])

    #performing the transformation
    new_rho = np.matmul(Q, rho)

    #magnitude of new position vector
    new_rho_mag = np.linalg.norm(new_rho)
    #unit vector in the direction of rho
    new_rho_hat = new_rho / new_rho_mag

    #Elevation angle
    elev_rad = asin(new_rho_hat[2])
    elev_deg = elev_rad*180/pi

    #Azimuth
    sinA = new_rho_hat[0]/cos(elev_rad)
    cosA = new_rho_hat[1]/cos(elev_rad)
    
    if sinA > 0:
        Azi_rad = acos(cosA)
    else:
        Azi_rad = (2*pi) - acos(cosA)
    
    Azi_deg = Azi_rad * 180 / pi


    return(Azi_deg,elev_deg,sat_long)






def sidereal_lt(year,month,day,hour,mins,secs,long):
    
    
    #first, work out sidereal time
    #we need to work out J0 from year, month and day (see algorythm 5.3, page 252)
    #equation 5.48

    #following example 5.6
    #equation 5.48
    J0 = (367 * year) - floor(7 * (year + floor((month + 9) / 12)) / 4) + floor(275 * month / 9) + day + 1721013.5
    
    #Eq 5.49
    T0 = (J0 - 2451545) / 36525

    #Greenwich sidereal time at 0 UT
    theta_G0 = 100.4606184 + (36000.77004 * T0) + (0.000387933 * T0**2) - (2.583E-8 * T0**3)    
    theta_G0 = zero_to_360(theta_G0)
    
    ut = hour + (mins/60) + (secs/3600)
    
    #Greenwich sidereal time at UT
    theta_G = theta_G0 + (360.98564724*ut/24);
        
    #This is the local sidereal time, adding the longitude onto the Greenwich sidereal time angle
    theta = theta_G + long
        
    #for when the angle lies outside of 0 - 360 deg
    theta = zero_to_360(theta)
        
    return(theta)





def sidereal_long(year,month,day,hour,mins,secs,theta):
    
    
    #first, work out sidereal time
    #we need to work out J0 from year, month and day (see algorythm 5.3, page 252)
    #equation 5.48

    #following example 5.6
    #equation 5.48
    J0 = (367 * year) - floor(7 * (year + floor((month + 9) / 12)) / 4) + floor(275 * month / 9) + day + 1721013.5
    
    #Eq 5.49
    T0 = (J0 - 2451545) / 36525

    #Greenwich sidereal time at 0 UT
    theta_G0 = 100.4606184 + (36000.77004 * T0) + (0.000387933 * T0**2) - (2.583E-8 * T0**3)    
    theta_G0 = zero_to_360(theta_G0)
    
    ut = hour + (mins/60) + (secs/3600)
    
    #Greenwich sidereal time at UT
    theta_G = theta_G0 + (360.98564724*ut/24);
    
    #Switching around the formula for the sidereal time to get the longitude
    long = theta - theta_G
        
    #for when the angle lies outside of +/-180 deg
    if long <= -180:
        long += 360
    if long > 180:
        long -= 360
        
    return(long)





def pause_til_safe():
    
    #remove these once testing is done
    #import csv
    #import sys
    #import time
    #import runpy
    
    #this is triggered when it's detected that the shutter status is not "open"
    #this happens either because the cloud sensor says it's not safe, or there's been a power outage
    #this routine checks both of these options, and holds until the coast is clear, then it reopens the
    #shutter and exits so that the rest of the operations can resume
    
    #first grab safety status
    folder = "C:/AAG_CloudWatcher/"
    file = folder+"CloudWatcher.csv"
    #file = folder+"CloudWatcher_test.csv"
    
    
    with open(file, newline='') as csvfile:
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
        time.sleep(120) #2 mins
        #for testing, only 5 seconds
        #time.sleep(5)
        
        with open(file, newline='') as csvfile:
        
            text2 = csv.reader(csvfile, delimiter=',', quotechar='"')

            row2 = list(text2)
        
            second_row = row2[1]            
            safe_status = second_row[16]
                
    
    print("Safe status detected!! Moving on to check power status...")
    
    file_scopedome = "C:/ScopeDome/ScopeDomeUSBCard_InternalSensors_Log.txt"
    #file_scopedome = "C:/ScopeDome/ScopeDomeUSBCard_InternalSensors_Log_test.txt"
    
    f = open(file_scopedome ,'r')

    status_records = []
    
    for line in f:
        
        columns = line.split()
        
        #0 if Power is okay, 1 - there's been a power failure (this will need confirming, but it's a godo guess for noww)
        power_status = columns[5]
 
        status_records.append(power_status)
        
    #number of lines at the end of this file we want to review for power failures
    n_lines = 20
    
    #going through the final parts of the file to see if there were any failures (i.e., if failure status not equal to 0)
    for iline in range(len(status_records)-n_lines,len(status_records)):
        #print(status_records[iline])
        if status_records[iline] != "0;":
            #print(status_records[iline])
            print("Power failure detectect in ScopeDome logs... halting operations")
            sys.exit()

    print("No power failure recorded... going back to resuming operations!")
    
    time.sleep(1)
    print("...")
    runpy.run_module(mod_name="OpenShutter")
    
    print(time.ctime())
    print("Shutter reopened... back to operations")
    #process_json_files_thread(folder_path, scheduled_observations)
    perform_scheduled_observations(teleobj, domeObj, scheduled_observations, folder_path)
        
    
    
    
    
    
def data_cleaning(CSV_dir,csv_file):
        
    utc_time = []
    jd_time = []
    XPOS = []
    YPOS = []
    RAs = []
    Decs = []
        
    g = open(CSV_dir+'/'+csv_file,'r')
   
    #getting length
    reader = csv.reader(g)
    lines = list(reader)
    n_lines = len(lines)
    
        
    
    if n_lines > 1:
        for line in lines[1:len(lines)+1]:
        
            columns = line#.split(",")
        
            t = Time(columns[0],format='isot',scale='utc')
            utc_time.append(str(t))
            jd_time.append(t.jd)
        
            XPOS.append(float(columns[1]))
            YPOS.append(float(columns[2]))
        
            RAs.append(float(columns[3]))            
            Decs.append(float(columns[4]))


    g.close()

    jd_time = np.array(jd_time)
    XPOS = np.array(XPOS)
    YPOS = np.array(YPOS)
    RAs = np.array(RAs)
    Decs = np.array(Decs)

    n_obs = len(jd_time)
    
    #Now go and calculate the temoporal derivatives of the angles and image positions
    d_t = np.zeros((n_obs,n_obs))
    d_XPOS = np.zeros((n_obs,n_obs))
    d_YPOS = np.zeros((n_obs,n_obs))
    d_POS = np.zeros((n_obs,n_obs))
    d_RA = np.zeros((n_obs,n_obs))
    d_Dec = np.zeros((n_obs,n_obs))
    d_Dec_RA = np.zeros((n_obs,n_obs))

        
    #first row of corrected angles data file
    ang_data_corr = Table(names=('Date', 'XPOS', 'YPOS', 'RA', 'DEC'), dtype=('S2', 'f4', 'f4','d','d'))
    row_count = 1

    for i_ind, i in enumerate(jd_time):
    
        for j_ind, j in enumerate(jd_time):
        
            d_t[i_ind,j_ind] = abs(jd_time[i_ind] - jd_time[j_ind]) * 24* 3600
        
            #zero time differences and the matrix above the diagonal is being set to NaN
            if d_t[i_ind,j_ind] == 0 or j_ind >= i_ind:
                d_XPOS[i_ind,j_ind] = math.nan
                d_YPOS[i_ind,j_ind] = math.nan
  
                d_POS[i_ind,j_ind] = math.nan
    
                d_RA[i_ind,j_ind] = math.nan
                d_Dec[i_ind,j_ind] = math.nan
        
            else:
            
                d_XPOS[i_ind,j_ind] = abs(XPOS[i_ind] - XPOS[j_ind])/d_t[i_ind,j_ind]
                d_YPOS[i_ind,j_ind] = abs(YPOS[i_ind] - YPOS[j_ind])/d_t[i_ind,j_ind]
  
                d_POS[i_ind,j_ind] = math.sqrt(d_XPOS[i_ind,j_ind]**2 + d_YPOS[i_ind,j_ind]**2)
    
                d_RA[i_ind,j_ind] = abs(RAs[i_ind] - RAs[j_ind])/d_t[i_ind,j_ind]
            
                #if d_RA[i_ind,j_ind] > 180:
                #   d_RA[i_ind,j_ind] -= 180
            
                d_Dec[i_ind,j_ind] = abs(Decs[i_ind] - Decs[j_ind])/d_t[i_ind,j_ind]
            
                d_Dec_RA[i_ind,j_ind] = math.sqrt(d_Dec[i_ind,j_ind]**2 + d_RA[i_ind,j_ind]**2)
            
            
            #specific criteria to spot Geostationary objects... 
            #the 5 pixels/s is an attempt to include Inclinded Geo objects, but this let's in a few false positives (which is okay, overall, for now)
            if d_POS[i_ind,j_ind] < 5 and (d_RA[i_ind,j_ind] > 0.0035 and d_RA[i_ind,j_ind] < 0.005):
                                
                #we had both i and j columns, with the intension that we can further clean by searching for "unique" measurements in the data
                ang_data_corr.add_row([utc_time[i_ind], XPOS[i_ind], YPOS[i_ind], RAs[i_ind], Decs[i_ind]])    
                ang_data_corr.add_row([utc_time[j_ind], XPOS[j_ind], YPOS[j_ind], RAs[j_ind], Decs[j_ind]])    
        
    if len(ang_data_corr) > 1:
            
        #cleaning the duplicate rows (works pretty well!!)
        ang_data_corr = unique(ang_data_corr)
            
        #writing all of the angles data
        cleaned_data_file = "corrected"+csv_file
            
        ang_data_corr.write(CSV_dir+'/'+cleaned_data_file,format = "ascii.csv",overwrite=True)        
        
        return(CSV_dir+'/'+cleaned_data_file)
    else:
        return(False)
    
    print("Data cleaning complete")






def csv_2_json(cleaned_csv,obs,expTime):
    
    
    df = pd.read_csv(cleaned_csv, sep=',')
    rx = len(df.XPOS)
    json_data_nest = []

    #testing
    #file_test = "UDL_creds_for_testing.txt"
    #dat_test = pd.read_csv(file_test)
    #user = dat_test.user[0]
    #password = dat_test.password[0]
    #service_endpoint_test = 'https://test.unifieddatalibrary.com/filedrop/udl-eo'
    #service_endpoint_test = 'https://test.unifieddatalibrary.com/udl/eoobservations'
    #service_endpoint_production = 'https://unifieddatalibrary.com/udl/eoobservation'
    
    for i in range (0,rx):

        json_data = {}
    

        json_data["classificationMarking"] = "U"
    
        json_data["obTime"] = str(df.Date.iloc[i]) + 'Z'
        json_data["ra"] = df.RA.iloc[i]
        json_data["declination"] = df.DEC.iloc[i]
        json_data["senlat"] = obs[0]
        json_data["senlon"] = obs[1]
        json_data["senalt"] = obs[2]
        json_data["expDuration"] = expTime
        json_data["source"] = "RMIT"
        json_data["idSensor"] = "RMIT-ROO"
        json_data["dataMode"]= "REAL"
        json_data["uct"] = "true"
    
        #adding the dictionary to the list of dictionaries for later UDL uploading
        json_data_nest.append(json_data)

    #save json file here    
    with open(cleaned_csv+'.json', 'w') as fp:
        json.dump(json_data_nest, fp, indent = 4)

    #UDL uploading_ Encrytion key needs to be regenerated, UDL posting not possible at this time..
    
    #with open('dirs.txt','rb') as dirs:
        #dir = str(dirs.read(),'utf-8')

    #with open(dir + 'udl_key.key','rb') as filekey:    
        #key = filekey.read()
    
    #fernet = Fernet(key)
    
    #Testing
    #file_encrypted = "UDL_creds_test.txt"
    #service_endpoint_test = 'https://test.unifieddatalibrary.com/filedrop/udl-eo'    
    
    #LIVE
    #file_encrypted = "UDL_creds.txt"
    #service_endpoint_production = 'https://unifieddatalibrary.com/filedrop/udl-eo'
    
    
    #with open(file_encrypted,'rb') as enc_file:
        #encrypted = enc_file.read()
    
    #decrypted = fernet.decrypt(encrypted)
    #s = str(decrypted,'utf-8')
    #datastring = StringIO(s)
    #dat = pd.read_csv(datastring,sep = ' ',index_col = False)
    #user = dat.user[0]
    #password = dat.password[0]
    
    
    #Testing
    #post_to_udl_json_data(service_endpoint_test, user, password, json_data_nest)
    
    #LIVE
    #post_to_udl_json_data(service_endpoint_production, user, password, json_data_nest)







def post_to_udl_json_data(udl_endpoint, username, unecrypted_password, json_data):
#
# perform udl interaction
#

    key = username + ":" + unecrypted_password
    authkey = base64.b64encode(key.encode('utf-8')).decode("ascii")

    udl_headers = {'accept': 'application/json',
                  'content-type': 'application/json',
                  'Authorization': 'Basic {auth}'.format(auth=authkey)}
    print("Invoking {url} endpoint".format(url=udl_endpoint))
    print("calling with {data}".format(data=json_data))

    response = requests.post(udl_endpoint,
                             data=json.dumps(json_data),
                             verify=True,
                             headers=udl_headers)
    response.raise_for_status()
    if response.ok:
        print("Completed data access at {url}".format(url=udl_endpoint))
    return response



start_time = time.time()
start_time_str = time.asctime()
    
#######################################
#TheSkyX objects
skyChartObj = win32com.client.Dispatch("TheSky64.sky6StarChart")

#TheskyX Telescope
teleObj = win32com.client.Dispatch("TheSky64.sky6RASCOMTele")
teleObj.Connect()


#TheSkyX Camera
camObj = win32com.client.Dispatch("TheSky64.ccdsoftCamera")
camObj.Connect()

#actual ASCOM dome object (for shutter status checks)
domeObj = win32com.client.Dispatch("Ascom.ScopeDomeUSBDome.DomeLS")
domeObj.Connected = True

#setting up SkyX's imagelink
imagelinkObj = win32com.client.Dispatch("TheSky64.ImageLink")
imagelinkObj.Scale = 1.1 

# exposure time (in sec) of each image
# This expTime needs to be passed on to the JSON execution routine
expTime = 1.0
#expTime = 3.0
#expTime = .001 #(for testing)

#setting camera exposure time
camObj.ExposureTime = expTime

#######################################

#ROO location (geodetic latitude then longitude, then height (in km))
#obs = [-(37+(40/60)+(50.32/3600)), 145+(3/60)+(41.91/3600), 0.1]  #(ROO)
obs = [-37.680589141, 145.061634327, 0.155083]  #surveying results for ROO

#minimum elevation considered
min_elev = 14

#number of images for each location
#(need to think about this... getting about 5.8 images per minute using this code...)
image_num = 5
#image_num = 3

angle_ran = [-180, 180] #this angle range is essentially the range of (sidereal) longitudes of GEO objects we'd like to explore (in ECI)
delta_angle = 0.5   #in degrees, should be determined by ~ size of camera FoV (with the focal reducer, 0.73 deg x 0.59 deg)
angles = np.arange((angle_ran[1]-angle_ran[0])/delta_angle)*delta_angle + angle_ran[0]

r_geo = 42164.0   #GEO radius

#initialising lists
azi = []
elev = []
sat_long = []

#azimuth range for GEO search 270,90 for full search, and if only a portion is to be searched, this can be changed here...
azi_ran = [309, 90] #Building blocks anything west of 308 azimuth, so it's a good starting point
#azi_ran = [42,47]

###################################
###################################
#range of longitudes that we're interested in (insert directly from SACT GEO wide area search job)
#implemented, but requires testing... looks like it's working to me
#Important note... the first item must be less than the second item
#long_ran = [-180,180]
#long_ran = [0,180]
long_ran = [90,180]

if long_ran[1] < long_ran[0]:
    print("The longitude range must start with the smaller value first")
    sys.exit()
###################################
###################################

cos=math.cos
sin=math.sin
pi=math.pi

for i in angles:
    X_i = r_geo * cos(i*pi/180.)
    Y_i = r_geo * sin(i*pi/180.)

    #position vector of GEO satellite at this angle
    r_sat = [X_i, Y_i, 0]

    #Performing calculation
    ans = r_to_azi_elev(r_sat,obs)

    #ans[2] is the satellite longitude (passed testing... looks good)

    #only considering the angles above the minimum elevation, and the range of azimuths given by azi_ran (above)
    
    #for situation where we're starting west of north (i.e., 270-360 deg azimuth) and finishing to the east of north
    if azi_ran[0] > azi_ran[1]:
        if ans[1] >= min_elev and ((ans[0] >= azi_ran[0] and ans[0] < 360) or (ans[0] >=0 and ans[0] <= azi_ran[1])) and (long_ran[0] <= ans[2] and long_ran[1] >= ans[2]):
            azi.append(ans[0])
            elev.append(ans[1])
            sat_long.append(ans[2])
    # the situation where both the start and finishing points are to the east or west
    else:
        if ans[1] >= min_elev and (ans[0] >= azi_ran[0] and ans[0] <= azi_ran[1]) and (long_ran[0] <= ans[2] and long_ran[1] >= ans[2]):
            azi.append(ans[0])
            elev.append(ans[1])
            sat_long.append(ans[2])


#if we want to scan East to West
#azi.reverse()
#elev.reverse()

print(azi)
print('***')
print(elev)
print('***')
print(sat_long)
#sys.exit()


#now, the trick is that perhaps you want say a couple of degs either side of the "base elevation" array, which is where the GEO belt is
d_elev_max = 1.5
delta_elev = 0.5

#d_elev_max = 0.5
#delta_elev = 0.5

#for scanning around the Geo belt
#d_elev = np.arange(d_elev_max*-1,(d_elev_max+delta_elev),delta_elev)

#for scanning only the Geo belt
d_elev = np.zeros(1)


#initialising indicies to help extract the correct azimuth and elevation values
index = 0

count = 0
repeat = True
azi2 = []
elev2 = []
# Brett's attempt at fixing issues aroubd failed regos, not working.. need to circle back
#while repeat == True:
    
    #if count == 0:
     #   repeat = False
    
for x in azi:
    azimuth = x
    
    print("Telescope is currently scanning at azimuth ",azimuth)
    
    for y in d_elev:
        perform_scheduled_observations(teleobj, domeObj, scheduled_observations, folder_path) # executing JSON file if any
    
        elevation = elev[index]+y
    
        print("Elevation ",elevation)
    
        #command to slew telescope
        try:
        
            teleObj.SlewToAzAlt(azimuth, elevation, 'Az_%d_Elev_%d' % (azimuth, elevation))
    
        except com_error as err:
        
            if err.excepinfo[5] == -2147198493:
        
                print("Encountered hard slew limit error... continuing on to next position")
            
                continue
        
            else:
                raise err
    
        if teleObj.Asynchronous == True:
            while teleObj.IsSlewComplete == False:
                time.sleep(0.1)
                #process_json_files_thread(folder_path, scheduled_observations)
    
        #turning tracking off (automatically goes to sidreal tracking after slew)
        teleObj.SetTracking(0,1,0,0)

        # light exposure
        #print("Taking exposure... NOOOOTT (we're testing it!!!)")
        #time.sleep(0.1)
    
        #initialising the any_sats flag... (new, this could be where I was stuffing up earlier...)
        any_sats = False
    
        #initialising the number of imagess that failed registration
        rego_fail_count = 0
        for i in range(1,image_num+1):
        
            #Doing a shutter status check
            #Shutter status ( 0 = open, 1 = closed, 2 = opening, 3 - closing, from trial and error)
            stat = domeObj.ShutterStatus

            if stat != 0:
                pause_til_safe()
        
            camObj.TakeImage()
            if camObj.Asynchronous == True:
                while camObj.IsExposureComplete == False:
                    time.sleep(0.1)
        
            last_image = camObj.LastImageFileName
            last_image_dir = camObj.AutoSavePath
        
            saved_csvs = last_image_dir+'/'+'CSVs'
            #just extracting the filename without the path for use in the CSV and PNG naming later on...
            fit_name = os.path.basename(last_image)
        
            #working out whether there are any possible satellites in the image
            possible_sats, xpos, ypos = satellite_detect(last_image_dir, last_image, True, True)
        
            #if there aren't any possible satellites, then don't bother taking more images... move on
            #if i == 1 and possible_sats == False:
            #    break
        
            #initialising angles data (in first of image batch) - this line here takes into account possibility that first image rego fails
            if i == 1:
                ang_data = Table(names=('Time', 'XPOS', 'YPOS', 'RA', 'DEC'), dtype=('S2', 'f4', 'f4','d','d'))
    
            if possible_sats == True:
                #do image registration...!
                print("Doing image registration...")
            
                image_link_success = False
            
                try:
                    imagelinkObj.PathToFITS = last_image
                    imagelinkObj.execute()
        
                except com_error as err:
        
                    if err.excepinfo[5] == 0:
                        print("Image Link failed...")
                        rego_fail_count += 1
                        #continue
                    else:
                        raise err
                else:
            
                    image_link_success = True
        
        
                if image_link_success == True:
                    print("Successful registration, extracting angles for suspected satellite(s)")
                
            
                    hdul = fits.open(last_image)
                    hdr = hdul[0].header
                    hdul.close()
                    date_obs = hdr['DATE-OBS']
                    exp = float(hdr['EXPTIME']) * u.s
                    latency = 0.81 * u.s
                
                    #time_corrections (camera latency, and taking mid-point of exposure)
                    t = Time(date_obs, format='isot',scale='utc') + TimeDelta(exp/2)
                    t += TimeDelta(latency)
                
                    date_obs_corr = str(t)
                
                    w = WCS(hdr)
            
                    #cycling through the number of objects in image and saving RA and Dec
                    for j, ind in enumerate(xpos):
                        sky = w.pixel_to_world(xpos[j],ypos[j])
                
                        print("Dec: ",sky.dec.deg)
                        print("RA: ",sky.ra.deg)
        
                        any_sats = True
                        ang_data.add_row([date_obs_corr, xpos[j], ypos[j], sky.ra.deg, sky.dec.deg])            
        
                if rego_fail_count >= 3:
                    azi2.append(azimuth)
                    elev2.append(elev[index])
                    repeat = True
            
            #only writing the data to file once the batch of 5 images have been taken, providing there are some angles that were extracted
            if i == image_num and any_sats == True:
                ang_data.write(saved_csvs+"/"+"angles"+fit_name+".csv",format = "ascii.csv")
                print("Angles saved")
            
            
                print("Performing data cleaning...")
                cleaned_csv = data_cleaning(saved_csvs,"angles"+fit_name+".csv")
            
                if cleaned_csv != False:
                    print("Now converting to JSON...")
                    json_dat = csv_2_json(cleaned_csv,obs,expTime)
                
    
    index += 1
# part of the code handling failed regos. 
   # if (repeat == True) & (count == 0):
     #   azi = azi2
      #  elev = elev2
       # index = 0
        #count = 1

print("Finished GEO search pattern")

end_time = time.time()
end_time_str = time.asctime()

print("Started at %s" % start_time_str)
print("Finished at %s" % end_time_str)


duration = end_time - start_time
print("Duration: %g seconds" % duration)
print("Duration: %g minutes" % (duration/60.))
print("Duration: %g hours" % (duration/3600.))



