import pandas as pd
Data={
    "N": [46,78,45],
    "P": [56,0,31],
    "K": [23,70,31],
    "Temperature": [33.67,51.78,41.51],
    "Humidity": [88,79,50],
    "Rainfall":[300.7874,400.4567,200.754],
    "Crop": ["Rice","Maize","Corn"]
}
df = pd.DataFrame(Data)
print(df.duplicated().sum())

print(df)
print("\nFirst row:")
print(df.head())
print("\nshape")
print(df.shape)
print("\ncolumns:")
print(df.columns)
print("\nInformation:")
print(df.info())
print("\nMissingvalue:")
print(df.isnull().sum())
print(df)
print(df.isnull().sum())
df["P"]=df["P"].fillna(df["P"].mean())
print("\nStatistics:")
print(df.describe())


