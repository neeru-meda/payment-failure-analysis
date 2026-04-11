import pandas as pd
import random
from datetime import datetime, timedelta
import os

random.seed(42)

channels = ['UPI', 'NEFT', 'RTGS', 'Card', 'Wallet']
banks    = ['SBI', 'HDFC', 'ICICI', 'Axis', 'Kotak']
reasons  = [
    'wrong_pin',
    'insufficient_funds',
    'bank_server_timeout',
    'network_failure',
    'invalid_account',
    'wrong_ifsc',
    'duplicate_txn',
    'account_blocked',
    'fraud_blocked',
    'outside_neft_hours'
]

def random_timestamp():
    start = datetime(2024, 1, 1)
    end   = datetime(2024, 3, 31)
    diff  = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, diff))

def should_fail(hour, day_of_month, channel):
    base = {
        'UPI':    0.22,
        'NEFT':   0.10,
        'RTGS':   0.06,
        'Card':   0.14,
        'Wallet': 0.18
    }[channel]

    if hour in [22, 23, 0, 1]:
        base = base * 3.0

    if day_of_month >= 28:
        base = base * 2.5

    base = min(base, 0.90)

    return random.random() < base

rows = []

for i in range(10000):
    ts      = random_timestamp()
    channel = random.choices(channels, weights=[35, 25, 10, 20, 10], k=1)[0]
    bank    = random.choice(banks)
    amount  = round(random.uniform(100, 50000), 2)
    hour    = ts.hour
    dom     = ts.day
    failed  = should_fail(hour, dom, channel)
    status  = 'Failed' if failed else 'Success'
    reason  = random.choice(reasons) if failed else 'none'

    rows.append({
        'transaction_id':    'TXN' + str(i + 1).zfill(6),
        'timestamp':         ts.strftime('%Y-%m-%d %H:%M:%S'),
        'payment_channel':   channel,
        'bank_name':         bank,
        'amount':            amount,
        'status':            status,
        'failure_reason':    reason,
        'hour':              hour,
        'day_of_month':      dom,
        'month':             ts.month,
        'day_of_week':       ts.strftime('%A'),
        'is_failed':         1 if failed else 0,
        'is_night_window':   1 if hour in [22, 23, 0, 1] else 0,
        'is_salary_window':  1 if dom >= 28 else 0,
    })

df = pd.DataFrame(rows)

os.makedirs('data', exist_ok=True)
df.to_csv('data/transactions_raw.csv', index=False)

total        = len(df)
failed_count = int(df['is_failed'].sum())
failure_rate = round(failed_count / total * 100, 1)

night_rate  = round(df[df['is_night_window']  == 1]['is_failed'].mean() * 100, 1)
day_rate    = round(df[df['is_night_window']  == 0]['is_failed'].mean() * 100, 1)
salary_rate = round(df[df['is_salary_window'] == 1]['is_failed'].mean() * 100, 1)
normal_rate = round(df[df['is_salary_window'] == 0]['is_failed'].mean() * 100, 1)

print("Total transactions  :", total)
print("Failed transactions :", failed_count)
print("Overall failure rate:", str(failure_rate) + "%")
print()
print("Failure rate by channel:")
channel_stats = df.groupby('payment_channel')['is_failed'].mean() * 100
for ch, rate in channel_stats.sort_values(ascending=False).items():
    print(" ", ch, "-", str(round(rate, 1)) + "%")
print()
print("Failure rate by bank:")
bank_stats = df.groupby('bank_name')['is_failed'].mean() * 100
for bk, rate in bank_stats.sort_values(ascending=False).items():
    print(" ", bk, "-", str(round(rate, 1)) + "%")
print()
print("Night window failure rate :", str(night_rate) + "%")
print("Daytime failure rate      :", str(day_rate) + "%")
print("Night is", str(round(night_rate / day_rate, 1)) + "x more likely to fail")
print()
print("Salary window failure rate:", str(salary_rate) + "%")
print("Normal days failure rate  :", str(normal_rate) + "%")
print("Salary days are", str(round(salary_rate / normal_rate, 1)) + "x more likely to fail")
print()
print("Saved to: data/transactions_raw.csv")
print("Columns :", list(df.columns))
