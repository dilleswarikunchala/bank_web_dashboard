from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import os

# ✅ FIX: Prevent matplotlib GUI error
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from io import BytesIO

app = Flask(__name__)

# ---------------------------------------------------
# FOLDERS
# ---------------------------------------------------
UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

UPLOAD_FILE = os.path.join(UPLOAD_FOLDER, "data.csv")
GRAPH_PATH = os.path.join(STATIC_FOLDER, "combined_chart.png")

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
def load_saved():
    if os.path.exists(UPLOAD_FILE):
        df = pd.read_csv(UPLOAD_FILE)

        df.columns = [c.strip() for c in df.columns]

        required = ["Date", "Description", "Category", "Amount", "Balance"]
        for col in required:
            if col not in df.columns:
                df[col] = ""

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
        df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce").ffill().fillna(0)

        return df
    else:
        return pd.DataFrame(columns=["Date", "Description", "Category", "Amount", "Balance"])

# ---------------------------------------------------
# SAVE DATA
# ---------------------------------------------------
def save_df(df):
    df = df[["Date", "Description", "Category", "Amount", "Balance"]]
    df.to_csv(UPLOAD_FILE, index=False)

# ---------------------------------------------------
# CREATE MONTHLY SUMMARY + GRAPH
# ---------------------------------------------------
def prepare_monthly_and_chart():

    df = load_saved()

    if df.empty:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    df["Deposit"] = df["Amount"].apply(lambda x: x if x > 0 else 0)
    df["Withdrawal"] = df["Amount"].apply(lambda x: abs(x) if x < 0 else 0)

    monthly = df.groupby("Month").agg(
        Deposit=("Deposit", "sum"),
        Withdrawal=("Withdrawal", "sum")
    ).reset_index()

    monthly["Balance"] = (monthly["Deposit"] - monthly["Withdrawal"]).cumsum()

    # --------- GRAPH ---------
    plt.figure(figsize=(10, 5))

    plt.plot(monthly["Month"], monthly["Deposit"], marker="o", label="Deposit")
    plt.plot(monthly["Month"], monthly["Withdrawal"], marker="o", label="Withdrawal")
    plt.plot(monthly["Month"], monthly["Balance"], marker="o", label="Balance")

    plt.xticks(rotation=45)
    plt.title("Monthly Deposit, Withdrawal & Balance")
    plt.legend()
    plt.tight_layout()

    plt.savefig(GRAPH_PATH)
    plt.close()

    return monthly

# ---------------------------------------------------
# ROUTES
# ---------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

# ✅ FIXED UPLOAD ROUTE
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if file and file.filename.endswith(".csv"):
        file.save(UPLOAD_FILE)

    return redirect(url_for("summary"))

# ---------------- ADD TRANSACTION ----------------
@app.route("/add_transaction", methods=["GET", "POST"])
def add_transaction():

    if request.method == "POST":

        df = load_saved()

        date = request.form.get("date")
        description = request.form.get("description")
        category = request.form.get("category")
        amount_raw = request.form.get("amount")

        try:
            amount = float(amount_raw)
        except:
            amount = 0.0

        if category.lower() in ["expense", "debit", "withdrawal"]:
            amount = -abs(amount)
        else:
            amount = abs(amount)

        if df.empty:
            balance = amount
        else:
            last_balance = df["Balance"].iloc[-1]
            balance = float(last_balance) + amount

        new_row = {
            "Date": date,
            "Description": description,
            "Category": category,
            "Amount": amount,
            "Balance": balance
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_df(df)

        return redirect(url_for("transactions"))

    return render_template("add_transaction.html")

# ---------------- TRANSACTIONS ----------------
@app.route("/transactions")
def transactions():
    df = load_saved()
    table_html = df.to_html(index=False, classes="table table-striped", float_format="%.2f")
    return render_template("transactions.html", table_html=table_html)

# ---------------- SUMMARY ----------------
@app.route("/summary")
def summary():

    monthly = prepare_monthly_and_chart()

    if monthly.empty:
        return render_template("summary.html", monthly_html=None)

    monthly_html = monthly.to_html(index=False, classes="table table-bordered", float_format="%.2f")
    return render_template("summary.html", monthly_html=monthly_html)

# ---------------- GRAPHS ----------------
@app.route("/graphs")
def graphs():

    monthly = prepare_monthly_and_chart()

    if monthly.empty:
        return render_template("graphs.html", graph_url=None)

    return render_template("graphs.html", graph_url="/static/combined_chart.png")

# ---------------- DOWNLOAD ----------------
@app.route("/download")
def download():

    monthly = prepare_monthly_and_chart()

    if monthly.empty:
        return "No data available", 400

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        monthly.to_excel(writer, index=False, sheet_name="Monthly Summary")
        load_saved().to_excel(writer, index=False, sheet_name="Transactions")

    output.seek(0)

    return send_file(
        output,
        download_name="bank_report.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)