import matplotlib.pyplot as plt
import pandas as pd

# Provided JSON data
data = {
  "result": [
    {"week_start": "2025-01-01", "week_end": "2025-01-05", "total_capacity": 19.126436781609193, "allocation_hours_planned": 4.9126436781609195},
    {"week_start": "2025-01-06", "week_end": "2025-01-12", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-01-13", "week_end": "2025-01-19", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-01-20", "week_end": "2025-01-26", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-01-27", "week_end": "2025-02-02", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-02-03", "week_end": "2025-02-09", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-02-10", "week_end": "2025-02-16", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-02-17", "week_end": "2025-02-23", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-02-24", "week_end": "2025-03-02", "total_capacity": 31.877394636015325, "allocation_hours_planned": 8.187739463601533},
    {"week_start": "2025-03-03", "week_end": "2025-03-09", "total_capacity": 31.877394636015325, "allocation_hours_planned": 10.187739463601533},
    {"week_start": "2025-03-10", "week_end": "2025-03-16", "total_capacity": 31.877394636015325, "allocation_hours_planned": 10.187739463601533},
    {"week_start": "2025-03-17", "week_end": "2025-03-23", "total_capacity": 31.877394636015325, "allocation_hours_planned": 10.187739463601533},
    {"week_start": "2025-03-24", "week_end": "2025-03-30", "total_capacity": 31.877394636015325, "allocation_hours_planned": 10.187739463601533},
    {"week_start": "2025-03-31", "week_end": "2025-04-06", "total_capacity": 31.877394636015325, "allocation_hours_planned": 6.037547892720307},
    {"week_start": "2025-04-07", "week_end": "2025-04-13", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-04-14", "week_end": "2025-04-20", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-04-21", "week_end": "2025-04-27", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-04-28", "week_end": "2025-05-04", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-05-05", "week_end": "2025-05-11", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-05-12", "week_end": "2025-05-18", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-05-19", "week_end": "2025-05-25", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-05-26", "week_end": "2025-06-01", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-06-02", "week_end": "2025-06-08", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-06-09", "week_end": "2025-06-15", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-06-16", "week_end": "2025-06-22", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-06-23", "week_end": "2025-06-29", "total_capacity": 31.877394636015325, "allocation_hours_planned": 5.0},
    {"week_start": "2025-06-30", "week_end": "2025-07-06", "total_capacity": 31.877394636015325, "allocation_hours_planned": 25.0},
    {"week_start": "2025-07-07", "week_end": "2025-07-13", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-07-14", "week_end": "2025-07-20", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-07-21", "week_end": "2025-07-27", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-07-28", "week_end": "2025-08-03", "total_capacity": 25.50191570881226, 
"allocation_hours_planned": 30.0},
    {"week_start": "2025-08-04", "week_end": "2025-08-10", "total_capacity": 0.0, "allocation_hours_planned": 30.0},
    {"week_start": "2025-08-11", "week_end": "2025-08-17", "total_capacity": 0.0, "allocation_hours_planned": 30.0},
    {"week_start": "2025-08-18", "week_end": "2025-08-24", "total_capacity": 0.0, "allocation_hours_planned": 30.0},
    {"week_start": "2025-08-25", "week_end": "2025-08-31", "total_capacity": 0.0, "allocation_hours_planned": 30.0},
    {"week_start": "2025-09-01", "week_end": "2025-09-07", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-09-08", "week_end": "2025-09-14", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-09-15", "week_end": "2025-09-21", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-09-22", "week_end": "2025-09-28", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-09-29", "week_end": "2025-10-05", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-10-06", "week_end": "2025-10-12", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-10-13", "week_end": "2025-10-19", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-10-20", "week_end": "2025-10-26", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-10-27", "week_end": "2025-11-02", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-11-03", "week_end": "2025-11-09", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-11-10", "week_end": "2025-11-16", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-11-17", "week_end": "2025-11-23", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-11-24", "week_end": "2025-11-30", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-12-01", "week_end": "2025-12-07", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-12-08", "week_end": "2025-12-14", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-12-15", "week_end": "2025-12-21", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-12-22", "week_end": "2025-12-28", "total_capacity": 31.877394636015325, "allocation_hours_planned": 30.0},
    {"week_start": "2025-12-29", "week_end": "2025-12-31", "total_capacity": 19.126436781609193, "allocation_hours_planned": 18.0}
  ]
}

# Convert the data to a DataFrame
df = pd.DataFrame(data['result'])

# Plotting
plt.figure(figsize=(14, 8))
plt.plot(df['week_start'], df['total_capacity'], label='Total Capacity', marker='o')
plt.plot(df['week_start'], df['allocation_hours_planned'], label='Planned Allocation', marker='*')
plt.xticks(rotation=90)
plt.xlabel('Week Start Date')
plt.ylabel('Hours')
plt.title('Weekly Capacity and Planned Allocation for Resource ID 2')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()