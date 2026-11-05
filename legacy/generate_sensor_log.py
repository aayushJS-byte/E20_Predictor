import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Simulate 14 days of historical hourly data
now = datetime.now()
# Create timestamps from 14 days ago up to right now
timestamps = [now - timedelta(hours=i) for i in range(14*24, -1, -1)]

np.random.seed(42)
base_water = 400
water_levels = []

# Simulate physical accumulation over time (with sensor noise)
for i in range(len(timestamps)):
    base_water += np.random.uniform(0.5, 2.5) # Gradual hourly moisture ingress
    water_levels.append(base_water + np.random.normal(0, 10)) # Add sensor noise
    
temp_swings = np.random.uniform(5, 22, len(timestamps))
humidities = np.random.uniform(50, 95, len(timestamps))
vapor_spaces = np.random.uniform(30, 80, len(timestamps))

df = pd.DataFrame({
    'timestamp': timestamps,
    'temp_swing_c': temp_swings,
    'humidity_pct': humidities,
    'vapor_space_vol': vapor_spaces,
    'water_ppm': water_levels
})

df.to_csv('data/sensor_log.csv', index=False)
print("Live sensor feed generated at data/sensor_log.csv")