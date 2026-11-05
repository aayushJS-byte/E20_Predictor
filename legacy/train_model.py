import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# Load data
df = pd.read_csv('data/synthetic_tank_data.csv')

X = df.drop('daily_ingress_ppm', axis=1)
y = df['daily_ingress_ppm']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train XGBoost
model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=200,
    learning_rate=0.05,
    max_depth=5
)
model.fit(X_train, y_train)

# Evaluate
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
print(f"Model trained. Mean Absolute Error: {mae:.2f} ppm/day")

# Save model
model.save_model('models/xgb_model.json')
print("Model saved to models/xgb_model.json")