# -*- coding: utf-8 -*-
"""
Created on Tue Nov  9 10:08:03 2021

This program is essentially the data pipeline for data that's been collected in "satellite tracking" mode (of one satellite, focusing on some QZSS data). 
The directory of the data that you want processed needs to be copied into a separate folder (because the astrometry overwrites the header) and given to this program. 
The code also leverages the satellite detection code in "Sat_detect_rego.py", not directly, but code copied into this program. 
It should then spit out a csv file with all the RA and Dec angles information listed.


@author: Dr Brett Carter, RMIT University

"""
from astropy.io import fits
import sys
import numpy as np
from astropy import units as u
import time
import win32com.client

import matplotlib.pyplot as plt
from astropy.visualization import astropy_mpl_style
plt.style.use(astropy_mpl_style)

from astropy.table import QTable, Table, Column
import matplotlib.pyplot as plt
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from photutils.background import Background2D, MedianBackground
from astropy.convolution import Gaussian2DKernel
from astropy.stats import gaussian_fwhm_to_sigma
from photutils.segmentation import detect_sources,deblend_sources
from photutils.segmentation import SourceCatalog
import os
import csv
from astropy.wcs import WCS
from astropy.time import Time, TimeDelta

from pywintypes import com_error


start_time=time.time()

#setting up SkyX's imagelink
imagelinkObj = win32com.client.Dispatch("TheSkyX.ImageLink")
imagelinkObj.Scale = 1.1

imagelinkresObj = win32com.client.Dispatch("TheSkyX.ImageLinkResults")



#fits_folder = "C:/Telescope Data/Main/November 08 2021/QZS-4/"
#fits_folder = "C:/Telescope Data/Test_QZS4/"
#fits_folder = "C:/Telescope Data/Test_QZS1/"
fits_folder = "C:/Telescope Data/Test_QZS1_uncorrectedtime/"
fits_folder = "C:/Telescope Data/QZS1_02032022/"
fits_folder = "C:/Telescope Data/QZS3_02032022/"
fits_folder = "C:/Telescope Data/QZS1R_02032022/"

fits_folder = "C:/Telescope Data/QZS1_03032022/"
fits_folder = "C:/Telescope Data/QZS3_03032022/"

fits_folder = "C:/Telescope Data/BSAT_02032022/"
fits_folder = "C:/Telescope Data/QZS1_09032022/"
fits_folder = "C:/Telescope Data/QZS3_09032022/"

#fits_folder = "C:/Telescope Data/QZS2_02052022/"

#need to redo... missing the satellite... it's too dim
fits_folder = "C:/Telescope Data/QZS3_02052022/"

#fits_folder = "C:/Telescope Data/QZS4_02052022/"


fits_folder = "C:/Telescope Data/Test_05/"
#ruined by dome light
fits_folder = "C:/Telescope Data/Control_QZS3/"

#follow up
fits_folder = "C:/Telescope Data/10_QZS4_2x2/"
fits_folder = "C:/Telescope Data/10_QZS3_2x2/"
#looks like a lot of images of nothing!!
fits_folder = "C:/Telescope Data/05_QZS4_2x2/"
#fits_folder = "C:/Telescope Data/05_QZS3_2x2/"

#fits_folder = "C:/Telescope Data/10_QZS4_1x1/"
#fits_folder = "C:/Telescope Data/10_QZS3_1x1/"
#fits_folder = "C:/Telescope Data/05_QZS4_1x1/"
#fits_folder = "C:/Telescope Data/05_QZS3_1x1/"

fits_folder = "C:/Telescope Data/GPS_2x2_1sec/"
fits_folder = "C:/Telescope Data/GPS5_2x2_05sec/"
fits_folder = "C:/Telescope Data/GPS18_2x2_05sec/"



saved_pngs_dir = fits_folder+"PNGs/"
saved_csvs = fits_folder+"CSVs/"

#maximum eccentricity for ellipse around source to be considered a possible satellite
max_ecc = 0.75

#minimum orientation difference (from the mean across the image) in order to be considered a possible satellite
orient_diff_min = 10 * u.deg

#minimum number of sources in an image to consider
min_sources = 10

#counter for the number of satellites found
count = 0
file_list = []
n_sats_file = []

#first row of angles data file
ang_data = Table(names=('Date-obs_corrected_midexp', 'XPOS', 'YPOS', 'RA', 'DEC', 'RMS', 'RMSX','RMSY'), dtype=('S2', 'f4', 'f4','d','d','d','d','d'))


for image_file in os.listdir(fits_folder):
    
    if image_file.endswith("fit"):
        print("Processing " +image_file)
    
        #fits.info(image_file)

        data1 = fits.getdata(fits_folder+image_file)
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
        #threshold = 3. * bkg.background_rms  # above the background
        threshold = 2. * bkg.background_rms  # above the background

    
        sigma = 3.0 * gaussian_fwhm_to_sigma  # FWHM = 3.
        kernel = Gaussian2DKernel(sigma, x_size=3, y_size=3)
        kernel.normalize()
        npixels = 25
        #needed for QZS-3 (dim bugger) or is it? QZS4 looks like the dim bastard...
        #npixels = 15
        #npixels = 10
        
        segm = detect_sources(data, threshold, npixels=25, kernel=kernel)
        #needed for QZS-3 (dim bugger)
        #segm = detect_sources(data, threshold, npixels=15, kernel=kernel)
        #segm = detect_sources(data, threshold, npixels=10, kernel=kernel)
        
        if segm is None:
            print("No sources found... bad image")
            
        if segm is not None:
            print("Deplending now.")
            segm_deblend = deblend_sources(data, segm, npixels=npixels,
                                           kernel=kernel, nlevels=32,
                                           contrast=0.001)
                
            print("Deplending complete.")
                
                
            norm = ImageNormalize(stretch=SqrtStretch())
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(35, 25))
            ax1.imshow(data, origin='lower', cmap='Greys_r', norm=norm);
            ax1.set_title('Data');
            cmap = segm.make_cmap(seed=123)
            ax2.imshow(segm, origin='lower', cmap=cmap, interpolation='nearest');
            ax2.set_title('Segmentation Image');
                
                
            cat = SourceCatalog(data, segm_deblend)
                
            tbl = cat.to_table()
                
            #writing table to csv file for further analysis...
            tbl.write(saved_csvs+image_file+".csv",format = "ascii.csv",overwrite=True)
                
            #cat_size = sys.getsizeof(cat)
                
            sats_in_image = 0.
            xpos = []
            ypos = []

            
            #mean_orient = np.mean(cat.orientation)
            #trying median, less sensitive to outliers... (except where there are few sources..., restricting to no less than 10 sources)
            if len(cat.orientation) > min_sources:
                mean_orient = np.median(cat.orientation)
            
                for i, element in enumerate(cat):
                    aperture = cat.kron_aperture[i]
                    ecc = cat.eccentricity[i]
                    orient_diff = abs(cat.orientation[i]-mean_orient)
                    
                    
                    #I had to insert this line because some of the apertures were being spat out as "Nonetype"... I'm assuming because the image quality??? But, images cleaned using AstroImageJ didn't work...
                    #if aperture is not None and (ecc < max_ecc or orient_diff > orient_diff_min):
                    if aperture is not None and (ecc < max_ecc or orient_diff > orient_diff_min) and (aperture.positions[0] > xmin_window and aperture.positions[0] < xmax_window) and (aperture.positions[1] > ymin_window and aperture.positions[1] < ymax_window):
                    
                        #if aperture is not None:
                            #aperture.plot(axes=ax1, color='white', lw=1.5)
                            aperture.plot(axes=ax2, color='white', lw=1.5)
                            
                            xpos.append(aperture.positions[0])
                            ypos.append(aperture.positions[1])
                            
                            ax2.plot(aperture.positions[0],aperture.positions[1],color = 'red', marker = 'o', markersize = 22, mfc='none');
                            print("Possible satellite found")
                            
                            count += 1                    
                            sats_in_image += 1
                    
            if sats_in_image >= 1:
                
                image_link_success = False
                
                try:
                    print("Doing astrometry")
                    imagelinkObj.PathToFITS = fits_folder+image_file
                    
                    #Time correction, before astrometry attempt (does this matter?? We're finding out...)
                    hdulist = fits.open(fits_folder+image_file, mode='update', verify='silentfix', ignore_missing_end=True)
                    
                    for hdu in hdulist:
                        if 'LATENCY' not in hdu.header:
                            hdu.header['LATENCY'] = ('YES', 'Time Latency corrected')
                            time_before = hdu.header['DATE-OBS']
                            exposure = float(hdu.header['EXPTIME']) * u.s
                            d = TimeDelta(0.81 * u.s)
                            formatted_time = Time(time_before) 
                            new_time = formatted_time + d
                            new_mid_time = new_time + (exposure/2)
                            #This should be uncommented out... 
                            hdu.header['DATE-OBS'] = str(new_time)
                            hdu.header['MIDTIME'] = str(new_mid_time)
                    hdulist.close()
                    
                    imagelinkObj.execute()
            
                except com_error as err:
            
                    if err.excepinfo[5] == 0:
                        print("Image Link failed... there aren't enough stars...")
                        continue
                    else:
                        raise err
                else:
                
                    image_link_success = True
            
                if image_link_success == True:
                    print("Successful registration, extracting angles for suspected satellite")
                    
                    rms = imagelinkresObj.solutionRMS
                    rms_x = imagelinkresObj.solutionRMSX
                    rms_y = imagelinkresObj.solutionRMSY
                
                    hdul = fits.open(fits_folder+image_file)
                    hdr = hdul[0].header
                    hdul.close()
                    ####
                    #testing timing issues... date_obs should be MIDTIME...
                    #line 202 needs to be updated as well!!!!
                    #date_obs = hdr['DATE-OBS']
                    date_obs = hdr['MIDTIME']
                    ####
                    #exp = float(hdr['EXPTIME']) * u.s                    
                    #latency = 0.81 * u.s
                    
                    #time_corrections (camera latency, and taking mid-point of exposure)
                    t = Time(date_obs, format='isot',scale='utc')# + TimeDelta(exp/2)
                    #t += TimeDelta(latency)
                    
                    date_obs_corr = str(t)
                    
                    
                    w = WCS(hdr)
                
                    #cycling through the number of objects in image and saving RA and Dec
                    for i, index in enumerate(xpos):
                        sky = w.pixel_to_world(xpos[i],ypos[i])
                    
                        print("Dec: ",sky.dec.deg)
                        print("RA: ",sky.ra.deg)
            
                        ang_data.add_row([date_obs_corr, xpos[i], ypos[i], sky.ra.deg, sky.dec.deg, rms, rms_x, rms_y])            
            
            
            
            
            plt.ioff()
            fig.savefig(saved_pngs_dir+image_file+".png");
            plt.close("all")
                            
            data = []
            data1 = []
            segm = []
            segm_deblend = []
            
            file_list.append([image_file,str(sats_in_image)])

#writing all of the angles data                    
ang_data.write(saved_csvs+image_file+"_angles.csv",format = "ascii.csv",overwrite=True)


print("Number of possible satellites found in batch: ", count)
file_list.append(["Total",str(count)])


with open(saved_csvs+"Overview.csv", 'w', newline='') as f:
     write = csv.writer(f)
     for val in file_list:
         write.writerow(val)

print("Results saved in "+saved_csvs+"Overview.csv")

end_time = time.time()

print("Started at %d", start_time)
print("Finished at %d", end_time)


duration = end_time - start_time
print("Duration: %g seconds" % duration)
print("Duration: %g minutes" % (duration/60.))
print("Duration: %g hours" % (duration/3600.))

