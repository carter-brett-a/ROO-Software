# -*- coding: utf-8 -*-
"""
Created on Mon Sep 25 20:25:30 2023

@author: Kaifur Rashed
"""

from astropy.coordinates import EarthLocation,SkyCoord
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import AltAz

import pandas as pd


stat_lat = -37.680589141
stat_lon = 145.061634327 
stat_h = 155

alt = 44.812497272835515
az = 17.61832170152756

t1 = "2023-06-12T07:07:07.76832Z" 
t2 = Time(t1, format='isot',scale='utc')


loc_dat = {"Name" : ["ROO"], "latitude" : [stat_lat], "longitude": [stat_lon], "height": [stat_h]}


loc_config = pd.DataFrame(data = loc_dat)
#loc_coords = loc_config['coordinates']
location = EarthLocation(lat=loc_config.iloc[0]['latitude']*u.deg,
                         lon = loc_config.iloc[0]['longitude']*u.deg,
                         height = loc_config.iloc[0]['height']*u.m)
altazframe = AltAz(obstime = t2, location = location)
coord = SkyCoord(alt = alt*u.deg, az = az*u.deg, frame = altazframe)
coord_icrs = coord.transform_to('icrs')
ra = coord_icrs.ra
dec = coord_icrs.dec

print("Right Ascension (α):", ra)
print("Declination (δ):", dec)
