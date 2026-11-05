import numpy as np
import pandas as pd
import os

np.random.seed(42)
n_samples = 10000

# Input Features
temp_swing_c = np.random.uniform(2, 25, n_samples)       # Diurnal temperature variation
humidity_pct = np.random.uniform(30, 98, n_samples)      # Ambient humidity
vapor_space_vol = np.random.uniform(10, 95, n_samples)   # % of tank filled with air
current_water_ppm = np.random.uniform(500, 4500, n_samples)

# Target: Daily Water Ingress (ppm)
# Physics approximation: Higher swing, humidity, and air volume pull in more moisture
base_ingress = (temp_swing_c * humidity_pct * vapor_space_vol) / 150
noise = np.random.normal(0, 15, n_samples)
daily_ingress_ppm = np.maximum(0, base_ingress + noise) # Cannot have negative ingress

df = pd.DataFrame({
    'temp_swing_c': temp_swing_c,
    'humidity_pct': humidity_pct,
    'vapor_space_vol': vapor_space_vol,
    'current_water_ppm': current_water_ppm,
    'daily_ingress_ppm': daily_ingress_ppm
})

df.to_csv('data/synthetic_tank_data.csv', index=False)
print("Synthetic data generated at data/synthetic_tank_data.csv")