import streamlit as st
import json
import uuid
from datetime import datetime
from supabase import create_client, Client

# Supabase config
SUPABASE_URL = "https://fokfznfepgdvqgfopqir.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZva2Z6bmZlcGdkdnFnZm9wcWlyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAxMjUwMTIsImV4cCI6MjA4NTcwMTAxMn0.ruTx9KWUu9RlNbIo2JZPkG0CR7zX_-CE6kFJ0Lo3X3g"

DEFAULT_BARDHAN_RATE = 28.0
DEFAULT_KANTA_RATE = 7.5


@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def parse_weight_to_quintals(weight: float) -> float:
    """Parse weight format: 528.5 = 5 quintals + 28.5 kgs"""
    quintals = int(weight // 100)
    kgs = weight % 100
    return quintals + (kgs / 100)


def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "user": None,
        "access_token": None,
        "refresh_token": None,
        "purchases": [],
        "sales": [],
        "purchase_entries": [],
        "sale_entries": [],
        "current_session_id": None,
        "session_name": "",
        "saved_sessions": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def login(email: str, password: str):
    supabase = get_supabase()
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.session_state.access_token = res.session.access_token
        st.session_state.refresh_token = res.session.refresh_token
        return None
    except Exception as e:
        return str(e)


def signup(email: str, password: str, name: str):
    supabase = get_supabase()
    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"name": name}},
        })
        return None
    except Exception as e:
        return str(e)


def logout():
    supabase = get_supabase()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.purchases = []
    st.session_state.sales = []
    st.session_state.purchase_entries = []
    st.session_state.sale_entries = []
    st.session_state.current_session_id = None
    st.session_state.session_name = ""


def fetch_sessions():
    supabase = get_supabase()
    user = st.session_state.user
    if not user:
        return []
    try:
        res = (
            supabase.table("trade_sessions")
            .select("*")
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .execute()
        )
        st.session_state.saved_sessions = res.data or []
        return st.session_state.saved_sessions
    except Exception as e:
        st.error(f"Error fetching sessions: {e}")
        return []


def save_session(session_name: str):
    supabase = get_supabase()
    user = st.session_state.user
    if not user:
        st.error("Please login first")
        return

    purchases = st.session_state.purchases
    sales = st.session_state.sales
    if not purchases and not sales:
        st.warning("Add at least one purchase or sale before saving")
        return

    total_purchase = sum(p["totalAmount"] for p in purchases)
    total_sale = sum(s["totalAmount"] for s in sales)

    data = {
        "user_id": user.id,
        "session_name": session_name or f"Session {datetime.now().strftime('%d/%m/%Y')}",
        "total_purchase_amount": total_purchase,
        "total_sale_amount": total_sale,
        "net_profit": total_sale - total_purchase,
        "purchases": purchases,
        "sales": sales,
    }

    try:
        if st.session_state.current_session_id:
            supabase.table("trade_sessions").update(data).eq(
                "id", st.session_state.current_session_id
            ).execute()
            st.success("Session updated!")
        else:
            supabase.table("trade_sessions").insert(data).execute()
            st.success("Session saved!")
        # Reset
        st.session_state.purchases = []
        st.session_state.sales = []
        st.session_state.purchase_entries = []
        st.session_state.sale_entries = []
        st.session_state.current_session_id = None
        st.session_state.session_name = ""
        fetch_sessions()
    except Exception as e:
        st.error(f"Error saving: {e}")


def load_session(session):
    purchases = session.get("purchases", [])
    sales = session.get("sales", [])
    # Add defaults for old data
    today = str(datetime.now().date())
    for p in purchases:
        p.setdefault("date", today)
        p.setdefault("amountPaid", 0)
        p.setdefault("amountReceived", 0)
        p.setdefault("bardhanRate", DEFAULT_BARDHAN_RATE)
        p.setdefault("bardhanAmount", 0)
    for s in sales:
        s.setdefault("date", today)
        s.setdefault("amountPaid", 0)
        s.setdefault("amountReceived", 0)
        s.setdefault("bardhanRate", DEFAULT_BARDHAN_RATE)
        s.setdefault("bardhanAmount", 0)
        s.setdefault("kantaRate", DEFAULT_KANTA_RATE)
        s.setdefault("kantaAmount", 0)

    st.session_state.purchases = purchases
    st.session_state.sales = sales
    st.session_state.session_name = session.get("session_name", "")
    st.session_state.current_session_id = session.get("id")
    st.session_state.purchase_entries = []
    st.session_state.sale_entries = []


def delete_session(session_id: str):
    supabase = get_supabase()
    try:
        supabase.table("trade_sessions").delete().eq("id", session_id).execute()
        fetch_sessions()
        st.success("Session deleted")
    except Exception as e:
        st.error(f"Error deleting: {e}")


# ── Auth Page ────────────────────────────────────────────────────────
def auth_page():
    st.markdown("# :hot_pepper: Chilli Trade Tracker")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            submitted = st.form_submit_button("Login")
            if submitted:
                if not email or not password:
                    st.error("Please fill all fields")
                else:
                    err = login(email, password)
                    if err:
                        st.error(err)
                    else:
                        st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            name = st.text_input("Name", key="signup_name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_pw")
            submitted = st.form_submit_button("Sign Up")
            if submitted:
                if not email or not password or not name:
                    st.error("Please fill all fields")
                else:
                    err = signup(email, password, name)
                    if err:
                        st.error(err)
                    else:
                        st.success("Account created! You can now login.")


# ── Main App ─────────────────────────────────────────────────────────
def main_app():
    user = st.session_state.user

    # Header
    col1, col2, col3 = st.columns([5, 3, 1])
    with col1:
        st.markdown("# :hot_pepper: Chilli Trade Tracker")
    with col2:
        st.caption(f"Logged in as **{user.email}**")
    with col3:
        if st.button("Logout"):
            logout()
            st.rerun()

    st.divider()

    # ── Session Controls ─────────────────────────────────────────────
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        session_name = st.text_input(
            "Session name",
            value=st.session_state.session_name,
            placeholder="e.g. Jan 2024 Batch",
            label_visibility="collapsed",
        )
        st.session_state.session_name = session_name
    with c2:
        if st.button("Save Session", type="primary", use_container_width=True):
            save_session(session_name)
            st.rerun()
    with c3:
        show_history = st.toggle("History", value=False)

    # ── Session History ──────────────────────────────────────────────
    if show_history:
        fetch_sessions()
        sessions = st.session_state.saved_sessions

        search = st.text_input("Search by trader name or session...", key="trader_search")
        if search:
            search_lower = search.lower()
            sessions = [
                s for s in sessions
                if search_lower in s.get("session_name", "").lower()
                or any(search_lower in p.get("traderName", "").lower() for p in s.get("purchases", []))
                or any(search_lower in sl.get("traderName", "").lower() for sl in s.get("sales", []))
            ]

        if not sessions:
            st.info("No saved sessions found" if not search else f'No sessions found for "{search}"')
        else:
            for sess in sessions:
                with st.container(border=True):
                    h1, h2 = st.columns([5, 2])
                    with h1:
                        st.markdown(f"**{sess['session_name']}**")
                        sellers = set(p.get("traderName", "") for p in sess.get("purchases", []))
                        buyers = set(s.get("traderName", "") for s in sess.get("sales", []))
                        if sellers:
                            st.caption(f"Sellers: {', '.join(sellers)}")
                        if buyers:
                            st.caption(f"Buyers: {', '.join(buyers)}")
                    with h2:
                        st.caption(sess.get("created_at", "")[:10])

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Purchase", f"₹{sess['total_purchase_amount']:.2f}")
                    m2.metric("Sale", f"₹{sess['total_sale_amount']:.2f}")
                    profit = sess["net_profit"]
                    m3.metric(
                        "Profit" if profit >= 0 else "Loss",
                        f"₹{abs(profit):.2f}",
                        delta=f"{'+'if profit>=0 else ''}{profit:.2f}",
                    )

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Load", key=f"load_{sess['id']}", use_container_width=True):
                            load_session(sess)
                            st.rerun()
                    with b2:
                        if st.button("Delete", key=f"del_{sess['id']}", use_container_width=True, type="secondary"):
                            delete_session(sess["id"])
                            st.rerun()

        st.divider()

    # ── Summary Dashboard ────────────────────────────────────────────
    purchases = st.session_state.purchases
    sales = st.session_state.sales

    if purchases or sales:
        total_purchase_amt = sum(p["totalAmount"] for p in purchases)
        total_sale_amt = sum(s["totalAmount"] for s in sales)
        net_profit = total_sale_amt - total_purchase_amt

        total_bags_purchased = sum(p["totalBags"] for p in purchases)
        total_bags_sold = sum(s["totalBags"] for s in sales)
        remaining = total_bags_purchased - total_bags_sold

        total_to_pay = sum(p["totalAmount"] for p in purchases)
        total_paid = sum(p.get("amountPaid", 0) for p in purchases)
        total_to_receive = sum(s["totalAmount"] for s in sales)
        total_received = sum(s.get("amountReceived", 0) for s in sales)

        # Profit
        st.subheader("Net Profit/Loss")
        p1, p2, p3 = st.columns(3)
        p1.metric("Total Purchase", f"₹{total_purchase_amt:.2f}")
        p2.metric("Total Sale", f"₹{total_sale_amt:.2f}")
        p3.metric(
            "Net Profit" if net_profit >= 0 else "Net Loss",
            f"₹{abs(net_profit):.2f}",
            delta=f"{'+'if net_profit>=0 else ''}{net_profit:.2f}",
        )

        # Inventory
        st.subheader("Inventory Status")
        i1, i2, i3 = st.columns(3)
        i1.metric("Bags Purchased", total_bags_purchased)
        i2.metric("Bags Sold", total_bags_sold)
        i3.metric("Remaining", remaining, delta=f"{remaining}")

        # Payment Status
        st.subheader("Payment Status")
        pay1, pay2 = st.columns(2)
        with pay1:
            st.markdown("**To Pay (Sellers)**")
            st.write(f"Total: ₹{total_to_pay:.2f}")
            st.write(f"Paid: :green[₹{total_paid:.2f}]")
            st.write(f"Pending: :orange[₹{(total_to_pay - total_paid):.2f}]")
        with pay2:
            st.markdown("**To Receive (Buyers)**")
            st.write(f"Total: ₹{total_to_receive:.2f}")
            st.write(f"Received: :green[₹{total_received:.2f}]")
            st.write(f"Pending: :orange[₹{(total_to_receive - total_received):.2f}]")

        st.divider()

    # ── Purchase & Sale Sections ─────────────────────────────────────
    tab_purchase, tab_sale = st.tabs(["📥 Purchase (Buying)", "📤 Sale (Selling)"])

    # ── PURCHASE TAB ─────────────────────────────────────────────────
    with tab_purchase:
        pt1, pt2 = st.columns([3, 1])
        with pt1:
            purchase_trader = st.text_input("Seller Name", key="purchase_trader_input", placeholder="Enter seller name")
        with pt2:
            from datetime import date as date_type
            purchase_date = st.date_input("Date", value=date_type.today(), key="purchase_date")

        st.markdown("**Add Entry**")
        with st.form("purchase_entry_form", clear_on_submit=True):
            ec1, ec2, ec3, ec4 = st.columns([1, 1.5, 1.5, 1])
            with ec1:
                p_bags = st.number_input("Bags", min_value=0, step=1, key="p_bags")
            with ec2:
                p_weight = st.number_input("Weight (528.5=5Q+28.5Kg)", min_value=0.0, step=0.1, key="p_weight", format="%.1f")
            with ec3:
                p_rate = st.number_input("Rate/Q (₹)", min_value=0.0, step=0.01, key="p_rate", format="%.2f")
            with ec4:
                add_entry = st.form_submit_button("+ Add")

            if add_entry and p_bags > 0 and p_weight > 0 and p_rate > 0:
                wq = parse_weight_to_quintals(p_weight)
                amt = wq * p_rate
                st.session_state.purchase_entries.append({
                    "id": str(uuid.uuid4()),
                    "bags": p_bags,
                    "weight": p_weight,
                    "weightInQuintals": round(wq, 3),
                    "ratePerQuintal": p_rate,
                    "totalAmount": round(amt, 2),
                })
                st.rerun()

        # Show current entries
        p_entries = st.session_state.purchase_entries
        if p_entries:
            import pandas as pd
            df = pd.DataFrame(p_entries)
            display_df = df[["bags", "weight", "weightInQuintals", "ratePerQuintal", "totalAmount"]].copy()
            display_df.columns = ["Bags", "Weight", "Weight (Q)", "Rate (₹)", "Amount (₹)"]
            display_df.index = range(1, len(display_df) + 1)
            st.dataframe(display_df, use_container_width=True)

            total_bags = sum(e["bags"] for e in p_entries)
            total_weight_q = sum(e["weightInQuintals"] for e in p_entries)
            entries_amount = sum(e["totalAmount"] for e in p_entries)
            st.write(f"**Totals:** {total_bags} bags | {total_weight_q:.3f} Q | ₹{entries_amount:.2f}")

            # Delete entry
            if len(p_entries) > 0:
                del_idx = st.selectbox("Remove entry #", range(1, len(p_entries) + 1), key="p_del_idx")
                if st.button("Remove Entry", key="p_remove"):
                    st.session_state.purchase_entries.pop(del_idx - 1)
                    st.rerun()

            # Bardhan
            st.markdown("**Charges**")
            bardhan_rate = st.number_input("Bardhan (₹/bag)", value=DEFAULT_BARDHAN_RATE, step=0.5, key="p_bardhan")
            bardhan_amt = total_bags * bardhan_rate
            grand_total = entries_amount + bardhan_amt
            st.info(f"Bardhan: {total_bags} bags × ₹{bardhan_rate} = **₹{bardhan_amt:.2f}** | Grand Total: **₹{grand_total:.2f}**")

            # Payment
            payment = st.number_input("Amount Paid to Seller (₹)", value=0.0, step=0.01, key="p_payment", format="%.2f")
            st.caption(f"Total: ₹{grand_total:.2f} | Pending: ₹{(grand_total - payment):.2f}")

            if st.button("Save Purchase", type="primary", key="save_purchase"):
                record = {
                    "id": str(uuid.uuid4()),
                    "date": str(purchase_date),
                    "traderName": purchase_trader or "Unknown Seller",
                    "entries": p_entries.copy(),
                    "totalBags": total_bags,
                    "totalWeightInQuintals": round(total_weight_q, 3),
                    "totalAmount": round(grand_total, 2),
                    "amountPaid": payment,
                    "amountReceived": 0,
                    "bardhanRate": bardhan_rate,
                    "bardhanAmount": round(bardhan_amt, 2),
                }
                st.session_state.purchases.append(record)
                st.session_state.purchase_entries = []
                st.rerun()

        # Saved purchases
        if purchases:
            st.markdown("### Saved Purchases")
            p_search = st.text_input("Search seller name...", key="purchase_search")
            display_purchases = purchases
            if p_search:
                display_purchases = [p for p in purchases if p_search.lower() in p.get("traderName", "").lower()]
            if not display_purchases:
                st.info(f'No purchases found for "{p_search}"')
            for idx, rec in enumerate(purchases):
                if p_search and p_search.lower() not in rec.get("traderName", "").lower():
                    continue
                with st.container(border=True):
                    st.markdown(f"**{rec['traderName']}** &nbsp; `{rec.get('date', '')}`")
                    st.write(
                        f"Bags: {rec['totalBags']} | Weight: {rec['totalWeightInQuintals']:.3f} Q | "
                        f"Amount: ₹{rec['totalAmount']:.2f}"
                    )
                    st.caption(
                        f"Bardhan: ₹{rec.get('bardhanAmount', 0):.2f} (@₹{rec.get('bardhanRate', DEFAULT_BARDHAN_RATE)}/bag)"
                    )
                    paid = rec.get("amountPaid", 0)
                    pending = rec["totalAmount"] - paid
                    st.write(f"Paid: :green[₹{paid:.2f}] | Pending: :orange[₹{pending:.2f}]")

                    uc1, uc2, uc3 = st.columns(3)
                    with uc1:
                        add_amt = st.number_input("Amount", min_value=0.0, step=0.01, key=f"padd_{idx}", format="%.2f")
                    with uc2:
                        if st.button("+ Add Payment", key=f"paddbt_{idx}"):
                            st.session_state.purchases[idx]["amountPaid"] = paid + add_amt
                            st.rerun()
                    with uc3:
                        if st.button("Delete", key=f"pdel_{idx}"):
                            st.session_state.purchases.pop(idx)
                            st.rerun()

    # ── SALE TAB ─────────────────────────────────────────────────────
    with tab_sale:
        st1, st2 = st.columns([3, 1])
        with st1:
            sale_trader = st.text_input("Buyer Name", key="sale_trader_input", placeholder="Enter buyer name")
        with st2:
            sale_date = st.date_input("Date", value=date_type.today(), key="sale_date")

        st.markdown("**Add Entry**")
        with st.form("sale_entry_form", clear_on_submit=True):
            sc1, sc2, sc3, sc4 = st.columns([1, 1.5, 1.5, 1])
            with sc1:
                s_bags = st.number_input("Bags", min_value=0, step=1, key="s_bags")
            with sc2:
                s_weight = st.number_input("Weight (528.5=5Q+28.5Kg)", min_value=0.0, step=0.1, key="s_weight", format="%.1f")
            with sc3:
                s_rate = st.number_input("Rate/Q (₹)", min_value=0.0, step=0.01, key="s_rate", format="%.2f")
            with sc4:
                add_s_entry = st.form_submit_button("+ Add")

            if add_s_entry and s_bags > 0 and s_weight > 0 and s_rate > 0:
                wq = parse_weight_to_quintals(s_weight)
                amt = wq * s_rate
                st.session_state.sale_entries.append({
                    "id": str(uuid.uuid4()),
                    "bags": s_bags,
                    "weight": s_weight,
                    "weightInQuintals": round(wq, 3),
                    "ratePerQuintal": s_rate,
                    "totalAmount": round(amt, 2),
                })
                st.rerun()

        s_entries = st.session_state.sale_entries
        if s_entries:
            import pandas as pd
            df = pd.DataFrame(s_entries)
            display_df = df[["bags", "weight", "weightInQuintals", "ratePerQuintal", "totalAmount"]].copy()
            display_df.columns = ["Bags", "Weight", "Weight (Q)", "Rate (₹)", "Amount (₹)"]
            display_df.index = range(1, len(display_df) + 1)
            st.dataframe(display_df, use_container_width=True)

            total_bags_s = sum(e["bags"] for e in s_entries)
            total_weight_q_s = sum(e["weightInQuintals"] for e in s_entries)
            entries_amount_s = sum(e["totalAmount"] for e in s_entries)
            st.write(f"**Totals:** {total_bags_s} bags | {total_weight_q_s:.3f} Q | ₹{entries_amount_s:.2f}")

            if len(s_entries) > 0:
                del_idx_s = st.selectbox("Remove entry #", range(1, len(s_entries) + 1), key="s_del_idx")
                if st.button("Remove Entry", key="s_remove"):
                    st.session_state.sale_entries.pop(del_idx_s - 1)
                    st.rerun()

            # Bardhan + Kanta
            st.markdown("**Charges**")
            ch1, ch2 = st.columns(2)
            with ch1:
                s_bardhan_rate = st.number_input("Bardhan (₹/bag)", value=DEFAULT_BARDHAN_RATE, step=0.5, key="s_bardhan")
            with ch2:
                s_kanta_rate = st.number_input("Kanta (₹/bag)", value=DEFAULT_KANTA_RATE, step=0.5, key="s_kanta")

            s_bardhan_amt = total_bags_s * s_bardhan_rate
            s_kanta_amt = total_bags_s * s_kanta_rate
            s_grand_total = entries_amount_s + s_bardhan_amt + s_kanta_amt
            st.info(
                f"Bardhan: ₹{s_bardhan_amt:.2f} | Kanta: ₹{s_kanta_amt:.2f} | "
                f"Grand Total: **₹{s_grand_total:.2f}**"
            )

            s_payment = st.number_input("Amount Received from Buyer (₹)", value=0.0, step=0.01, key="s_payment", format="%.2f")
            st.caption(f"Total: ₹{s_grand_total:.2f} | Pending: ₹{(s_grand_total - s_payment):.2f}")

            if st.button("Save Sale", type="primary", key="save_sale"):
                record = {
                    "id": str(uuid.uuid4()),
                    "date": str(sale_date),
                    "traderName": sale_trader or "Unknown Buyer",
                    "entries": s_entries.copy(),
                    "totalBags": total_bags_s,
                    "totalWeightInQuintals": round(total_weight_q_s, 3),
                    "totalAmount": round(s_grand_total, 2),
                    "amountPaid": 0,
                    "amountReceived": s_payment,
                    "bardhanRate": s_bardhan_rate,
                    "bardhanAmount": round(s_bardhan_amt, 2),
                    "kantaRate": s_kanta_rate,
                    "kantaAmount": round(s_kanta_amt, 2),
                }
                st.session_state.sales.append(record)
                st.session_state.sale_entries = []
                st.rerun()

        # Saved sales
        if sales:
            st.markdown("### Saved Sales")
            s_search = st.text_input("Search buyer name...", key="sale_search")
            display_sales = sales
            if s_search:
                display_sales = [s for s in sales if s_search.lower() in s.get("traderName", "").lower()]
            if not display_sales:
                st.info(f'No sales found for "{s_search}"')
            for idx, rec in enumerate(sales):
                if s_search and s_search.lower() not in rec.get("traderName", "").lower():
                    continue
                with st.container(border=True):
                    st.markdown(f"**{rec['traderName']}** &nbsp; `{rec.get('date', '')}`")
                    st.write(
                        f"Bags: {rec['totalBags']} | Weight: {rec['totalWeightInQuintals']:.3f} Q | "
                        f"Amount: ₹{rec['totalAmount']:.2f}"
                    )
                    st.caption(
                        f"Bardhan: ₹{rec.get('bardhanAmount', 0):.2f} (@₹{rec.get('bardhanRate', DEFAULT_BARDHAN_RATE)}/bag) | "
                        f"Kanta: ₹{rec.get('kantaAmount', 0):.2f} (@₹{rec.get('kantaRate', DEFAULT_KANTA_RATE)}/bag)"
                    )
                    received = rec.get("amountReceived", 0)
                    pending = rec["totalAmount"] - received
                    st.write(f"Received: :green[₹{received:.2f}] | Pending: :orange[₹{pending:.2f}]")

                    uc1, uc2, uc3 = st.columns(3)
                    with uc1:
                        add_amt = st.number_input("Amount", min_value=0.0, step=0.01, key=f"sadd_{idx}", format="%.2f")
                    with uc2:
                        if st.button("+ Add Payment", key=f"saddbt_{idx}"):
                            st.session_state.sales[idx]["amountReceived"] = received + add_amt
                            st.rerun()
                    with uc3:
                        if st.button("Delete", key=f"sdel_{idx}"):
                            st.session_state.sales.pop(idx)
                            st.rerun()

    # Reset button
    if purchases or sales:
        st.divider()
        if st.button("Reset All", type="secondary"):
            st.session_state.purchases = []
            st.session_state.sales = []
            st.session_state.purchase_entries = []
            st.session_state.sale_entries = []
            st.session_state.current_session_id = None
            st.session_state.session_name = ""
            st.rerun()


# ── Main ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Chilli Trade Tracker", page_icon="🌶️", layout="wide")
init_session_state()

if st.session_state.user is None:
    auth_page()
else:
    main_app()
