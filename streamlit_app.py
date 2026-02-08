import streamlit as st
import uuid
from datetime import datetime, date as date_type
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
        "page": "main",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Recover auth session from cached supabase client after page refresh
    if st.session_state.user is None:
        try:
            supabase = get_supabase()
            session = supabase.auth.get_session()
            if session and session.refresh_token:
                refreshed = supabase.auth.refresh_session(session.refresh_token)
                if refreshed and refreshed.session:
                    st.session_state.user = refreshed.session.user
                    st.session_state.access_token = refreshed.session.access_token
                    st.session_state.refresh_token = refreshed.session.refresh_token
                else:
                    st.session_state.user = session.user
                    st.session_state.access_token = session.access_token
                    st.session_state.refresh_token = session.refresh_token
            elif session:
                st.session_state.user = session.user
                st.session_state.access_token = session.access_token
                st.session_state.refresh_token = session.refresh_token
        except Exception:
            pass


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
    today = str(datetime.now().date())
    for p in purchases:
        p.setdefault("date", today)
        p.setdefault("amountPaid", 0)
        p.setdefault("amountReceived", 0)
        p.setdefault("bardhanRate", DEFAULT_BARDHAN_RATE)
        p.setdefault("bardhanAmount", 0)
        p.setdefault("linkedSales", [])  # Track which sales this purchase was sold to
    for s in sales:
        s.setdefault("date", today)
        s.setdefault("amountPaid", 0)
        s.setdefault("amountReceived", 0)
        s.setdefault("bardhanRate", DEFAULT_BARDHAN_RATE)
        s.setdefault("bardhanAmount", 0)
        s.setdefault("kantaRate", DEFAULT_KANTA_RATE)
        s.setdefault("kantaAmount", 0)
        s.setdefault("sourceSeller", "")  # Track which seller this sale came from

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


def rename_trader_in_all_sessions(old_name: str, new_name: str, trader_type: str):
    """Rename a trader (seller or buyer) across all sessions."""
    supabase = get_supabase()
    sessions = st.session_state.saved_sessions

    updated_count = 0
    for sess in sessions:
        modified = False
        if trader_type == "seller":
            for p in sess.get("purchases", []):
                if p.get("traderName", "").lower() == old_name.lower():
                    p["traderName"] = new_name
                    modified = True
            # Also update sourceSeller in sales
            for s in sess.get("sales", []):
                if s.get("sourceSeller", "").lower() == old_name.lower():
                    s["sourceSeller"] = new_name
                    modified = True
        else:  # buyer
            for s in sess.get("sales", []):
                if s.get("traderName", "").lower() == old_name.lower():
                    s["traderName"] = new_name
                    modified = True

        if modified:
            # Recalculate totals
            total_purchase = sum(p["totalAmount"] for p in sess.get("purchases", []))
            total_sale = sum(s["totalAmount"] for s in sess.get("sales", []))

            try:
                supabase.table("trade_sessions").update({
                    "purchases": sess.get("purchases", []),
                    "sales": sess.get("sales", []),
                    "total_purchase_amount": total_purchase,
                    "total_sale_amount": total_sale,
                    "net_profit": total_sale - total_purchase,
                }).eq("id", sess["id"]).execute()
                updated_count += 1
            except Exception as e:
                st.error(f"Error updating session {sess['session_name']}: {e}")

    return updated_count


def update_trader_payment(trader_name: str, trader_type: str, add_amount: float = 0, set_amount: float = None):
    """Update payment for a trader across all sessions. Returns number of sessions updated."""
    supabase = get_supabase()
    sessions = st.session_state.saved_sessions

    updated_count = 0
    remaining_to_add = add_amount

    for sess in sessions:
        modified = False
        if trader_type == "seller":
            for p in sess.get("purchases", []):
                if p.get("traderName", "").lower() == trader_name.lower():
                    if set_amount is not None:
                        p["amountPaid"] = set_amount
                        modified = True
                    elif remaining_to_add > 0:
                        current_paid = p.get("amountPaid", 0)
                        pending = p.get("totalAmount", 0) - current_paid
                        if pending > 0:
                            to_add = min(remaining_to_add, pending)
                            p["amountPaid"] = current_paid + to_add
                            remaining_to_add -= to_add
                            modified = True
        else:  # buyer
            for s in sess.get("sales", []):
                if s.get("traderName", "").lower() == trader_name.lower():
                    if set_amount is not None:
                        s["amountReceived"] = set_amount
                        modified = True
                    elif remaining_to_add > 0:
                        current_received = s.get("amountReceived", 0)
                        pending = s.get("totalAmount", 0) - current_received
                        if pending > 0:
                            to_add = min(remaining_to_add, pending)
                            s["amountReceived"] = current_received + to_add
                            remaining_to_add -= to_add
                            modified = True

        if modified:
            try:
                supabase.table("trade_sessions").update({
                    "purchases": sess.get("purchases", []),
                    "sales": sess.get("sales", []),
                }).eq("id", sess["id"]).execute()
                updated_count += 1
            except Exception as e:
                st.error(f"Error updating session {sess['session_name']}: {e}")

    return updated_count


def get_trader_records(trader_name: str, trader_type: str):
    """Get all records for a specific trader across sessions."""
    sessions = st.session_state.saved_sessions
    records = []

    for sess in sessions:
        if trader_type == "seller":
            for p in sess.get("purchases", []):
                if p.get("traderName", "").lower() == trader_name.lower():
                    records.append({
                        "session_id": sess["id"],
                        "session_name": sess["session_name"],
                        "record_id": p.get("id"),
                        "date": p.get("date", ""),
                        "bags": p.get("totalBags", 0),
                        "amount": p.get("totalAmount", 0),
                        "paid": p.get("amountPaid", 0),
                        "pending": p.get("totalAmount", 0) - p.get("amountPaid", 0),
                    })
        else:  # buyer
            for s in sess.get("sales", []):
                if s.get("traderName", "").lower() == trader_name.lower():
                    records.append({
                        "session_id": sess["id"],
                        "session_name": sess["session_name"],
                        "record_id": s.get("id"),
                        "date": s.get("date", ""),
                        "bags": s.get("totalBags", 0),
                        "amount": s.get("totalAmount", 0),
                        "received": s.get("amountReceived", 0),
                        "pending": s.get("totalAmount", 0) - s.get("amountReceived", 0),
                    })

    return records


def update_specific_record(session_id: str, record_id: str, trader_type: str, field: str, value: float):
    """Update a specific field in a specific record."""
    supabase = get_supabase()
    sessions = st.session_state.saved_sessions

    for sess in sessions:
        if sess["id"] != session_id:
            continue

        records = sess.get("purchases" if trader_type == "seller" else "sales", [])
        for rec in records:
            if rec.get("id") == record_id:
                rec[field] = value
                try:
                    supabase.table("trade_sessions").update({
                        "purchases": sess.get("purchases", []),
                        "sales": sess.get("sales", []),
                    }).eq("id", sess["id"]).execute()
                    return True
                except Exception as e:
                    st.error(f"Error updating: {e}")
                    return False
    return False


def get_aggregate_stats(sessions):
    """Calculate aggregate stats from all sessions."""
    total_purchase = 0
    total_sale = 0
    total_bags_purchased = 0
    total_bags_sold = 0
    total_paid = 0
    total_received = 0
    all_sellers = {}  # name -> {bags, amount, paid, pending, sales_to (buyers)}
    all_buyers = {}   # name -> {bags, amount, received, pending, bought_from (sellers)}

    for sess in sessions:
        for p in sess.get("purchases", []):
            name = p.get("traderName", "Unknown")
            amt = p.get("totalAmount", 0)
            bags = p.get("totalBags", 0)
            paid = p.get("amountPaid", 0)

            total_purchase += amt
            total_bags_purchased += bags
            total_paid += paid

            if name not in all_sellers:
                all_sellers[name] = {"bags": 0, "amount": 0, "paid": 0, "sold_to": set()}
            all_sellers[name]["bags"] += bags
            all_sellers[name]["amount"] += amt
            all_sellers[name]["paid"] += paid

        for s in sess.get("sales", []):
            buyer_name = s.get("traderName", "Unknown")
            source_seller = s.get("sourceSeller", "")
            amt = s.get("totalAmount", 0)
            bags = s.get("totalBags", 0)
            received = s.get("amountReceived", 0)

            total_sale += amt
            total_bags_sold += bags
            total_received += received

            if buyer_name not in all_buyers:
                all_buyers[buyer_name] = {"bags": 0, "amount": 0, "received": 0, "bought_from": set()}
            all_buyers[buyer_name]["bags"] += bags
            all_buyers[buyer_name]["amount"] += amt
            all_buyers[buyer_name]["received"] += received

            # Track relationships
            if source_seller:
                all_buyers[buyer_name]["bought_from"].add(source_seller)
                if source_seller in all_sellers:
                    all_sellers[source_seller]["sold_to"].add(buyer_name)

    # Add pending to each trader and convert sets to lists
    for name in all_sellers:
        all_sellers[name]["pending"] = all_sellers[name]["amount"] - all_sellers[name]["paid"]
        all_sellers[name]["sold_to"] = list(all_sellers[name]["sold_to"])
    for name in all_buyers:
        all_buyers[name]["pending"] = all_buyers[name]["amount"] - all_buyers[name]["received"]
        all_buyers[name]["bought_from"] = list(all_buyers[name]["bought_from"])

    return {
        "total_purchase": total_purchase,
        "total_sale": total_sale,
        "net_profit": total_sale - total_purchase,
        "total_bags_purchased": total_bags_purchased,
        "total_bags_sold": total_bags_sold,
        "remaining_bags": total_bags_purchased - total_bags_sold,
        "total_paid": total_paid,
        "total_received": total_received,
        "pending_to_pay": total_purchase - total_paid,
        "pending_to_receive": total_sale - total_received,
        "sellers": all_sellers,
        "buyers": all_buyers,
    }


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

    # Fetch all sessions for aggregate stats
    fetch_sessions()
    sessions = st.session_state.saved_sessions
    stats = get_aggregate_stats(sessions)

    # Get list of all seller names for dropdown
    all_seller_names = sorted(stats['sellers'].keys()) if stats['sellers'] else []

    # ══════════════════════════════════════════════════════════════════
    # CREATE/EDIT SESSION (Moved to TOP)
    # ══════════════════════════════════════════════════════════════════
    st.subheader("➕ Create/Edit Session")

    c1, c2 = st.columns([4, 1])
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

    # Current session summary
    purchases = st.session_state.purchases
    sales = st.session_state.sales

    if purchases or sales:
        st.markdown("#### Current Session Summary")
        total_purchase_amt = sum(p["totalAmount"] for p in purchases)
        total_sale_amt = sum(s["totalAmount"] for s in sales)
        net_profit = total_sale_amt - total_purchase_amt

        total_bags_purchased = sum(p["totalBags"] for p in purchases)
        total_bags_sold = sum(s["totalBags"] for s in sales)

        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("Purchase", f"₹{total_purchase_amt:.2f}")
        cp2.metric("Sale", f"₹{total_sale_amt:.2f}")
        cp3.metric(
            "Profit" if net_profit >= 0 else "Loss",
            f"₹{abs(net_profit):.2f}",
            delta=f"{'+'if net_profit>=0 else ''}{net_profit:.2f}",
        )
        st.caption(f"Bags: {total_bags_purchased} purchased, {total_bags_sold} sold, {total_bags_purchased - total_bags_sold} remaining")

    # ── Purchase & Sale Sections ─────────────────────────────────────
    tab_purchase, tab_sale = st.tabs(["📥 Purchase (Buying)", "📤 Sale (Selling)"])

    # ── PURCHASE TAB ─────────────────────────────────────────────────
    with tab_purchase:
        pt1, pt2 = st.columns([3, 1])
        with pt1:
            purchase_trader = st.text_input("Seller Name", key="purchase_trader_input", placeholder="Enter seller name")
        with pt2:
            purchase_date = st.date_input("Date", value=date_type.today(), key="purchase_date")

        st.markdown("**Add Entry**")
        with st.form("purchase_entry_form", clear_on_submit=True):
            ec1, ec2, ec3, ec4 = st.columns([1, 1.5, 1.5, 1])
            with ec1:
                p_bags_str = st.text_input("Bags", key="p_bags", placeholder="e.g. 5")
            with ec2:
                p_weight_str = st.text_input("Weight", key="p_weight", placeholder="528.5=5Q+28.5Kg")
            with ec3:
                p_rate_str = st.text_input("Rate/Q (₹)", key="p_rate", placeholder="e.g. 15000")
            with ec4:
                add_entry = st.form_submit_button("+ Add")

            # Parse inputs
            try:
                p_bags = int(p_bags_str) if p_bags_str.strip() else 0
            except ValueError:
                p_bags = 0
            try:
                p_weight = float(p_weight_str) if p_weight_str.strip() else 0.0
            except ValueError:
                p_weight = 0.0
            try:
                p_rate = float(p_rate_str) if p_rate_str.strip() else 0.0
            except ValueError:
                p_rate = 0.0

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

            if len(p_entries) > 0:
                del_idx = st.selectbox("Remove entry #", range(1, len(p_entries) + 1), key="p_del_idx")
                if st.button("Remove Entry", key="p_remove"):
                    st.session_state.purchase_entries.pop(del_idx - 1)
                    st.rerun()

            st.markdown("**Charges**")
            bardhan_rate = st.number_input("Bardhan (₹/bag)", value=DEFAULT_BARDHAN_RATE, step=0.5, key="p_bardhan")
            bardhan_amt = total_bags * bardhan_rate
            grand_total = entries_amount + bardhan_amt
            st.info(f"Bardhan: {total_bags} bags × ₹{bardhan_rate} = **₹{bardhan_amt:.2f}** | Grand Total: **₹{grand_total:.2f}**")

            payment_str = st.text_input("Amount Paid to Seller (₹)", key="p_payment", placeholder="Enter amount paid")
            try:
                payment = float(payment_str) if payment_str.strip() else 0.0
            except ValueError:
                payment = 0.0
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
                    "linkedSales": [],
                }
                st.session_state.purchases.append(record)
                st.session_state.purchase_entries = []
                st.rerun()

        # Saved purchases in current session
        if purchases:
            st.markdown("### Saved Purchases (Current Session)")
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
                        add_amt_str = st.text_input("Amount", key=f"padd_{idx}", placeholder="₹")
                        try:
                            add_amt = float(add_amt_str) if add_amt_str.strip() else 0.0
                        except ValueError:
                            add_amt = 0.0
                    with uc2:
                        if st.button("+ Add Payment", key=f"paddbt_{idx}"):
                            if add_amt > 0:
                                st.session_state.purchases[idx]["amountPaid"] = paid + add_amt
                                st.rerun()
                    with uc3:
                        if st.button("Delete", key=f"pdel_{idx}"):
                            st.session_state.purchases.pop(idx)
                            st.rerun()

    # ── SALE TAB ─────────────────────────────────────────────────────
    with tab_sale:
        # Get current session's seller names for linking
        current_sellers = list(set(p.get("traderName", "") for p in purchases)) if purchases else []

        st1, st2, st3 = st.columns([2, 2, 1])
        with st1:
            sale_trader = st.text_input("Buyer Name", key="sale_trader_input", placeholder="Enter buyer name")
        with st2:
            # Source seller dropdown - who did this stock come from?
            source_options = ["-- Select Source Seller --"] + current_sellers + all_seller_names
            # Remove duplicates while preserving order
            source_options = list(dict.fromkeys(source_options))
            source_seller = st.selectbox("Source Seller (bought from)", options=source_options, key="source_seller")
            if source_seller == "-- Select Source Seller --":
                source_seller = ""
        with st3:
            sale_date = st.date_input("Date", value=date_type.today(), key="sale_date")

        st.markdown("**Add Entry**")
        with st.form("sale_entry_form", clear_on_submit=True):
            sc1, sc2, sc3, sc4 = st.columns([1, 1.5, 1.5, 1])
            with sc1:
                s_bags_str = st.text_input("Bags", key="s_bags", placeholder="e.g. 5")
            with sc2:
                s_weight_str = st.text_input("Weight", key="s_weight", placeholder="528.5=5Q+28.5Kg")
            with sc3:
                s_rate_str = st.text_input("Rate/Q (₹)", key="s_rate", placeholder="e.g. 16000")
            with sc4:
                add_s_entry = st.form_submit_button("+ Add")

            # Parse inputs
            try:
                s_bags = int(s_bags_str) if s_bags_str.strip() else 0
            except ValueError:
                s_bags = 0
            try:
                s_weight = float(s_weight_str) if s_weight_str.strip() else 0.0
            except ValueError:
                s_weight = 0.0
            try:
                s_rate = float(s_rate_str) if s_rate_str.strip() else 0.0
            except ValueError:
                s_rate = 0.0

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

            s_payment_str = st.text_input("Amount Received from Buyer (₹)", key="s_payment", placeholder="Enter amount received")
            try:
                s_payment = float(s_payment_str) if s_payment_str.strip() else 0.0
            except ValueError:
                s_payment = 0.0
            st.caption(f"Total: ₹{s_grand_total:.2f} | Pending: ₹{(s_grand_total - s_payment):.2f}")

            if st.button("Save Sale", type="primary", key="save_sale"):
                record = {
                    "id": str(uuid.uuid4()),
                    "date": str(sale_date),
                    "traderName": sale_trader or "Unknown Buyer",
                    "sourceSeller": source_seller,  # Track source
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

        # Saved sales in current session
        if sales:
            st.markdown("### Saved Sales (Current Session)")
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
                    header_text = f"**{rec['traderName']}** &nbsp; `{rec.get('date', '')}`"
                    if rec.get("sourceSeller"):
                        header_text += f" &nbsp; (from: {rec['sourceSeller']})"
                    st.markdown(header_text)
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
                        add_amt_str = st.text_input("Amount", key=f"sadd_{idx}", placeholder="₹")
                        try:
                            add_amt = float(add_amt_str) if add_amt_str.strip() else 0.0
                        except ValueError:
                            add_amt = 0.0
                    with uc2:
                        if st.button("+ Add Payment", key=f"saddbt_{idx}"):
                            if add_amt > 0:
                                st.session_state.sales[idx]["amountReceived"] = received + add_amt
                                st.rerun()
                    with uc3:
                        if st.button("Delete", key=f"sdel_{idx}"):
                            st.session_state.sales.pop(idx)
                            st.rerun()

    # Reset button
    if purchases or sales:
        st.divider()
        if st.button("Reset Current Session", type="secondary"):
            st.session_state.purchases = []
            st.session_state.sales = []
            st.session_state.purchase_entries = []
            st.session_state.sale_entries = []
            st.session_state.current_session_id = None
            st.session_state.session_name = ""
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # OVERALL DASHBOARD (All Sessions Summary)
    # ══════════════════════════════════════════════════════════════════
    st.subheader("📊 Overall Dashboard (All Sessions)")

    # Net Profit/Loss
    d1, d2, d3 = st.columns(3)
    d1.metric("Total Purchase", f"₹{stats['total_purchase']:.2f}")
    d2.metric("Total Sale", f"₹{stats['total_sale']:.2f}")
    profit = stats['net_profit']
    d3.metric(
        "Net Profit" if profit >= 0 else "Net Loss",
        f"₹{abs(profit):.2f}",
        delta=f"{'+'if profit>=0 else ''}{profit:.2f}",
    )

    # Inventory Status
    i1, i2, i3 = st.columns(3)
    i1.metric("Bags Purchased", stats['total_bags_purchased'])
    i2.metric("Bags Sold", stats['total_bags_sold'])
    i3.metric("Remaining Bags", stats['remaining_bags'],
              delta=f"{stats['remaining_bags']}" if stats['remaining_bags'] != 0 else None)

    # Payment Status Summary
    pay1, pay2 = st.columns(2)
    with pay1:
        st.markdown("**💰 To Pay (Sellers)**")
        st.write(f"Total: ₹{stats['total_purchase']:.2f}")
        st.write(f"Paid: :green[₹{stats['total_paid']:.2f}]")
        st.write(f"Pending: :orange[₹{stats['pending_to_pay']:.2f}]")
    with pay2:
        st.markdown("**💵 To Receive (Buyers)**")
        st.write(f"Total: ₹{stats['total_sale']:.2f}")
        st.write(f"Received: :green[₹{stats['total_received']:.2f}]")
        st.write(f"Pending: :orange[₹{stats['pending_to_receive']:.2f}]")

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # SELLERS & BUYERS SECTIONS (with edit functionality)
    # ══════════════════════════════════════════════════════════════════
    seller_tab, buyer_tab = st.tabs(["👥 Sellers (I buy from)", "🏪 Buyers (I sell to)"])

    # ── SELLERS TAB ───────────────────────────────────────────────────
    with seller_tab:
        sellers = stats['sellers']
        if not sellers:
            st.info("No sellers yet. Add purchases to see seller connections.")
        else:
            # Edit seller name section
            with st.expander("✏️ Edit/Merge Seller Names"):
                st.caption("Use this to fix typos or merge duplicate sellers")
                edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 1])
                with edit_col1:
                    old_seller = st.selectbox("Select seller to rename", options=[""] + list(sellers.keys()), key="old_seller")
                with edit_col2:
                    new_seller_name = st.text_input("New name", key="new_seller_name")
                with edit_col3:
                    st.write("")  # Spacer
                    st.write("")
                    if st.button("Rename", key="rename_seller", type="primary"):
                        if old_seller and new_seller_name and old_seller != new_seller_name:
                            count = rename_trader_in_all_sessions(old_seller, new_seller_name, "seller")
                            if count > 0:
                                st.success(f"Renamed '{old_seller}' to '{new_seller_name}' in {count} session(s)")
                                st.rerun()
                            else:
                                st.warning("No sessions updated")
                        else:
                            st.error("Please select a seller and enter a new name")

            seller_search = st.text_input("Search sellers...", key="seller_search")
            filtered_sellers = {k: v for k, v in sellers.items()
                              if not seller_search or seller_search.lower() in k.lower()}

            if not filtered_sellers:
                st.info(f'No sellers found for "{seller_search}"')
            else:
                for name, data in sorted(filtered_sellers.items(), key=lambda x: x[1]['pending'], reverse=True):
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.markdown(f"**{name}**")
                            st.write(f"Bags: {data['bags']} | Total: ₹{data['amount']:.2f}")
                            if data.get('sold_to'):
                                st.caption(f"Sold to: {', '.join(data['sold_to'])}")
                        with c2:
                            st.write(f"Paid: :green[₹{data['paid']:.2f}]")
                            if data['pending'] > 0:
                                st.write(f"Pending: :orange[₹{data['pending']:.2f}]")
                            else:
                                st.write(f"Pending: :green[₹0.00] ✓")

                        # Edit section
                        with st.expander("✏️ Edit Records"):
                            records = get_trader_records(name, "seller")
                            if records:
                                for i, rec in enumerate(records):
                                    st.markdown(f"**{rec['session_name']}** - {rec['date']}")
                                    rc1, rc2, rc3 = st.columns([2, 2, 2])
                                    with rc1:
                                        st.write(f"Bags: {rec['bags']}")
                                        st.write(f"Amount: ₹{rec['amount']:.2f}")
                                    with rc2:
                                        st.write(f"Paid: :green[₹{rec['paid']:.2f}]")
                                        st.write(f"Pending: :orange[₹{rec['pending']:.2f}]")
                                    with rc3:
                                        new_paid_str = st.text_input("Set paid to", key=f"sel_{name}_{i}", placeholder="₹")
                                        if st.button("Update", key=f"selbtn_{name}_{i}"):
                                            if new_paid_str.strip():
                                                try:
                                                    new_paid = float(new_paid_str)
                                                    if update_specific_record(rec['session_id'], rec['record_id'], "seller", "amountPaid", new_paid):
                                                        st.success("Updated!")
                                                        fetch_sessions()
                                                        st.rerun()
                                                except ValueError:
                                                    st.error("Invalid number")
                                    st.divider()

    # ── BUYERS TAB ────────────────────────────────────────────────────
    with buyer_tab:
        buyers = stats['buyers']
        if not buyers:
            st.info("No buyers yet. Add sales to see buyer connections.")
        else:
            # Edit buyer name section
            with st.expander("✏️ Edit/Merge Buyer Names"):
                st.caption("Use this to fix typos or merge duplicate buyers")
                edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 1])
                with edit_col1:
                    old_buyer = st.selectbox("Select buyer to rename", options=[""] + list(buyers.keys()), key="old_buyer")
                with edit_col2:
                    new_buyer_name = st.text_input("New name", key="new_buyer_name")
                with edit_col3:
                    st.write("")  # Spacer
                    st.write("")
                    if st.button("Rename", key="rename_buyer", type="primary"):
                        if old_buyer and new_buyer_name and old_buyer != new_buyer_name:
                            count = rename_trader_in_all_sessions(old_buyer, new_buyer_name, "buyer")
                            if count > 0:
                                st.success(f"Renamed '{old_buyer}' to '{new_buyer_name}' in {count} session(s)")
                                st.rerun()
                            else:
                                st.warning("No sessions updated")
                        else:
                            st.error("Please select a buyer and enter a new name")

            buyer_search = st.text_input("Search buyers...", key="buyer_search")
            filtered_buyers = {k: v for k, v in buyers.items()
                             if not buyer_search or buyer_search.lower() in k.lower()}

            if not filtered_buyers:
                st.info(f'No buyers found for "{buyer_search}"')
            else:
                for name, data in sorted(filtered_buyers.items(), key=lambda x: x[1]['pending'], reverse=True):
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.markdown(f"**{name}**")
                            st.write(f"Bags: {data['bags']} | Total: ₹{data['amount']:.2f}")
                            if data.get('bought_from'):
                                st.caption(f"Bought from: {', '.join(data['bought_from'])}")
                        with c2:
                            st.write(f"Received: :green[₹{data['received']:.2f}]")
                            if data['pending'] > 0:
                                st.write(f"Pending: :orange[₹{data['pending']:.2f}]")
                            else:
                                st.write(f"Pending: :green[₹0.00] ✓")

                        # Edit section
                        with st.expander("✏️ Edit Records"):
                            records = get_trader_records(name, "buyer")
                            if records:
                                for i, rec in enumerate(records):
                                    st.markdown(f"**{rec['session_name']}** - {rec['date']}")
                                    rc1, rc2, rc3 = st.columns([2, 2, 2])
                                    with rc1:
                                        st.write(f"Bags: {rec['bags']}")
                                        st.write(f"Amount: ₹{rec['amount']:.2f}")
                                    with rc2:
                                        st.write(f"Received: :green[₹{rec['received']:.2f}]")
                                        st.write(f"Pending: :orange[₹{rec['pending']:.2f}]")
                                    with rc3:
                                        new_received_str = st.text_input("Set received to", key=f"buy_{name}_{i}", placeholder="₹")
                                        if st.button("Update", key=f"buybtn_{name}_{i}"):
                                            if new_received_str.strip():
                                                try:
                                                    new_received = float(new_received_str)
                                                    if update_specific_record(rec['session_id'], rec['record_id'], "buyer", "amountReceived", new_received):
                                                        st.success("Updated!")
                                                        fetch_sessions()
                                                        st.rerun()
                                                except ValueError:
                                                    st.error("Invalid number")
                                    st.divider()

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # SAVED SESSIONS
    # ══════════════════════════════════════════════════════════════════
    st.subheader("📋 Saved Sessions")

    if not sessions:
        st.info("No saved sessions yet. Create and save a session above.")
    else:
        session_search = st.text_input("Search sessions by name or trader...", key="session_search")

        filtered_sessions = sessions
        if session_search:
            search_lower = session_search.lower()
            filtered_sessions = [
                s for s in sessions
                if search_lower in s.get("session_name", "").lower()
                or any(search_lower in p.get("traderName", "").lower() for p in s.get("purchases", []))
                or any(search_lower in sl.get("traderName", "").lower() for sl in s.get("sales", []))
            ]

        if not filtered_sessions:
            st.info(f'No sessions found for "{session_search}"')
        else:
            for sess in filtered_sessions:
                with st.container(border=True):
                    h1, h2 = st.columns([5, 2])
                    with h1:
                        st.markdown(f"**{sess['session_name']}**")
                        sess_sellers = set(p.get("traderName", "") for p in sess.get("purchases", []))
                        sess_buyers = set(s.get("traderName", "") for s in sess.get("sales", []))
                        if sess_sellers:
                            st.caption(f"Sellers: {', '.join(sess_sellers)}")
                        if sess_buyers:
                            st.caption(f"Buyers: {', '.join(sess_buyers)}")
                    with h2:
                        st.caption(sess.get("created_at", "")[:10])

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Purchase", f"₹{sess['total_purchase_amount']:.2f}")
                    m2.metric("Sale", f"₹{sess['total_sale_amount']:.2f}")
                    sess_profit = sess["net_profit"]
                    m3.metric(
                        "Profit" if sess_profit >= 0 else "Loss",
                        f"₹{abs(sess_profit):.2f}",
                        delta=f"{'+'if sess_profit>=0 else ''}{sess_profit:.2f}",
                    )

                    # Bags info
                    sess_bags_purchased = sum(p.get("totalBags", 0) for p in sess.get("purchases", []))
                    sess_bags_sold = sum(s.get("totalBags", 0) for s in sess.get("sales", []))
                    st.caption(f"Bags: {sess_bags_purchased} purchased, {sess_bags_sold} sold, {sess_bags_purchased - sess_bags_sold} remaining")

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Load", key=f"load_{sess['id']}", use_container_width=True):
                            load_session(sess)
                            st.rerun()
                    with b2:
                        if st.button("Delete", key=f"del_{sess['id']}", use_container_width=True, type="secondary"):
                            delete_session(sess["id"])
                            st.rerun()


# ── Main ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Chilli Trade Tracker", page_icon="🌶️", layout="wide")
init_session_state()

if st.session_state.user is None:
    auth_page()
else:
    main_app()
