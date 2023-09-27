# -*- coding: utf-8 -*-
"""
Created on Tue Aug 22 16:37:48 2023

@author: E123197
"""

import math
import numpy as np

# Given values
lambda_observer = 238  # East longitude in degrees
phi_observer = 38     # Latitude in degrees
LST = 215.1           # Local Sidereal Time in degrees
A = 214.3  # Azimuth in degrees
a = 43 # Angular elevation in degrees

# Convert angles to radians
lambda_observer_rad = math.radians(lambda_observer)
phi_observer_rad = math.radians(phi_observer)
LST_rad = math.radians(LST)
A_rad = math.radians(A)
a_rad = math.radians(a)

# Calculate transformation matrix Q
Q = np.array([
    [math.sin(LST_rad), -math.cos(LST_rad), 0],
    [math.cos(LST_rad), math.sin(LST_rad), 0],
    [0, 0, 1]
])

# Calculate topocentric horizon components of ρ
rho_gx = np.array([
    [math.cos(a_rad) * math.sin(A_rad)],
    [math.cos(a_rad) * math.cos(A_rad)],
    [math.sin(a_rad)]
])

# Calculate topocentric equatorial components of ρ
rho_gX = np.dot(Q, rho_gx)

# Calculate unit vector ρ
rho_unit = rho_gX / np.linalg.norm(rho_gX)

# Calculate topocentric equatorial right ascension (α) and declination (δ)
alpha = math.atan2(rho_unit[1], rho_unit[0])
declination = math.asin(rho_unit[2])

# Convert angles back to degrees
alpha_deg = math.degrees(alpha)
declination_deg = math.degrees(declination)

print("Jupiter's Right Ascension (α):", alpha_deg)
print("Jupiter's Declination (δ):", declination_deg)

