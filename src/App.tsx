import React, { useState, useEffect } from 'react';
import './App.css';
import { supabase, DbTradeSession } from './supabaseClient';
import Auth from './Auth';
import { User } from '@supabase/supabase-js';

interface ChilliEntry {
  id: string;
  bags: number;
  weight: number;
  weightInQuintals: number;
  ratePerQuintal: number;
  totalAmount: number;
}

interface TradeRecord {
  id: string;
  traderName: string;
  entries: ChilliEntry[];
  totalBags: number;
  totalWeightInQuintals: number;
  totalAmount: number;
  amountPaid: number; // For purchases: amount paid to seller
  amountReceived: number; // For sales: amount received from buyer
  bardhanRate: number; // Bardhan charge per bag (default ₹28)
  bardhanAmount: number; // totalBags × bardhanRate
  kantaRate?: number; // Kanta charge per bag (default ₹7.5, only for sales)
  kantaAmount?: number; // totalBags × kantaRate (only for sales)
}

// Default rates
const DEFAULT_BARDHAN_RATE = 28;
const DEFAULT_KANTA_RATE = 7.5;

// Parse weight format: 528.5 = 5 quintals + 28.5 kgs
const parseWeightToQuintals = (weight: number): number => {
  const quintals = Math.floor(weight / 100);
  const kgs = weight % 100;
  return quintals + (kgs / 100);
};

// Session timeout (10 minutes = 600000 ms)
const SESSION_TIMEOUT = 10 * 60 * 1000;

function App() {
  // Auth state
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // Session state
  const [sessionName, setSessionName] = useState('');
  const [savedSessions, setSavedSessions] = useState<DbTradeSession[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(false);
  const [traderSearch, setTraderSearch] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null); // Track if editing existing session

  // Purchase state
  const [purchases, setPurchases] = useState<TradeRecord[]>([]);
  const [purchaseTrader, setPurchaseTrader] = useState('');
  const [purchaseEntries, setPurchaseEntries] = useState<ChilliEntry[]>([]);
  const [purchaseInput, setPurchaseInput] = useState({ bags: '', weight: '', rate: '' });
  const [purchasePayment, setPurchasePayment] = useState('');
  const [editingPurchasePayment, setEditingPurchasePayment] = useState<string | null>(null);
  const [editPurchaseAmount, setEditPurchaseAmount] = useState('');
  const [purchaseBardhanRate, setPurchaseBardhanRate] = useState(DEFAULT_BARDHAN_RATE.toString());

  // Sales state
  const [sales, setSales] = useState<TradeRecord[]>([]);
  const [saleTrader, setSaleTrader] = useState('');
  const [saleEntries, setSaleEntries] = useState<ChilliEntry[]>([]);
  const [saleInput, setSaleInput] = useState({ bags: '', weight: '', rate: '' });
  const [salePayment, setSalePayment] = useState('');
  const [editingSalePayment, setEditingSalePayment] = useState<string | null>(null);
  const [editSaleAmount, setEditSaleAmount] = useState('');
  const [saleBardhanRate, setSaleBardhanRate] = useState(DEFAULT_BARDHAN_RATE.toString());
  const [saleKantaRate, setSaleKantaRate] = useState(DEFAULT_KANTA_RATE.toString());

  // Session timeout tracking
  const [lastActivity, setLastActivity] = useState(Date.now());

  // Check auth state on mount - always require fresh login
  useEffect(() => {
    const initAuth = async () => {
      // Clear any existing session on app launch to require fresh login
      await supabase.auth.signOut();
      setUser(null);
      setAuthLoading(false);
    };

    initAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Session timeout - auto logout after 10 minutes of inactivity
  useEffect(() => {
    if (!user) return;

    const resetTimer = () => {
      setLastActivity(Date.now());
    };

    // Listen for user activity
    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
    events.forEach(event => {
      window.addEventListener(event, resetTimer);
    });

    // Check for timeout every minute
    const timeoutChecker = setInterval(async () => {
      if (Date.now() - lastActivity > SESSION_TIMEOUT) {
        alert('Session expired due to inactivity. Please login again.');
        await supabase.auth.signOut();
        setUser(null);
      }
    }, 60000); // Check every minute

    return () => {
      events.forEach(event => {
        window.removeEventListener(event, resetTimer);
      });
      clearInterval(timeoutChecker);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, lastActivity]);

  // Load saved sessions when user logs in
  useEffect(() => {
    if (user) {
      fetchSessions();

      // Set up real-time subscription
      const subscription = supabase
        .channel('trade_sessions')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'trade_sessions' }, () => {
          fetchSessions();
        })
        .subscribe();

      return () => {
        subscription.unsubscribe();
      };
    }
  }, [user]);

  const fetchSessions = async () => {
    if (!user) return;

    const { data, error } = await supabase
      .from('trade_sessions')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false });

    if (error) {
      console.error('Error fetching sessions:', error);
    } else {
      setSavedSessions(data || []);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    handleResetAll();
    setSavedSessions([]);
  };

  // Add entry to purchase
  const handleAddPurchaseEntry = () => {
    if (!purchaseInput.bags || !purchaseInput.weight || !purchaseInput.rate) {
      alert('Please fill bags, weight, and rate');
      return;
    }
    const bags = parseFloat(purchaseInput.bags);
    const weight = parseFloat(purchaseInput.weight);
    const ratePerQuintal = parseFloat(purchaseInput.rate);
    const weightInQuintals = parseWeightToQuintals(weight);
    const totalAmount = weightInQuintals * ratePerQuintal;

    setPurchaseEntries([...purchaseEntries, {
      id: Date.now().toString(),
      bags,
      weight,
      weightInQuintals,
      ratePerQuintal,
      totalAmount
    }]);
    setPurchaseInput({ bags: '', weight: '', rate: '' });
  };

  // Add entry to sale
  const handleAddSaleEntry = () => {
    if (!saleInput.bags || !saleInput.weight || !saleInput.rate) {
      alert('Please fill bags, weight, and rate');
      return;
    }
    const bags = parseFloat(saleInput.bags);
    const weight = parseFloat(saleInput.weight);
    const ratePerQuintal = parseFloat(saleInput.rate);
    const weightInQuintals = parseWeightToQuintals(weight);
    const totalAmount = weightInQuintals * ratePerQuintal;

    setSaleEntries([...saleEntries, {
      id: Date.now().toString(),
      bags,
      weight,
      weightInQuintals,
      ratePerQuintal,
      totalAmount
    }]);
    setSaleInput({ bags: '', weight: '', rate: '' });
  };

  // Delete entry
  const handleDeletePurchaseEntry = (id: string) => {
    setPurchaseEntries(purchaseEntries.filter(e => e.id !== id));
  };

  const handleDeleteSaleEntry = (id: string) => {
    setSaleEntries(saleEntries.filter(e => e.id !== id));
  };

  // Save purchase record
  const handleSavePurchase = () => {
    if (purchaseEntries.length === 0) {
      alert('Please add at least one entry');
      return;
    }

    const totalBags = purchaseEntries.reduce((sum, e) => sum + e.bags, 0);
    const totalWeightInQuintals = purchaseEntries.reduce((sum, e) => sum + e.weightInQuintals, 0);
    const entriesAmount = purchaseEntries.reduce((sum, e) => sum + e.totalAmount, 0);
    const amountPaid = parseFloat(purchasePayment) || 0;
    const bardhanRate = parseFloat(purchaseBardhanRate) || DEFAULT_BARDHAN_RATE;
    const bardhanAmount = totalBags * bardhanRate;
    const totalAmount = entriesAmount + bardhanAmount; // Include bardhan in total

    const newRecord: TradeRecord = {
      id: Date.now().toString(),
      traderName: purchaseTrader || 'Unknown Seller',
      entries: [...purchaseEntries],
      totalBags,
      totalWeightInQuintals,
      totalAmount,
      amountPaid,
      amountReceived: 0,
      bardhanRate,
      bardhanAmount
    };

    setPurchases([...purchases, newRecord]);
    setPurchaseTrader('');
    setPurchaseEntries([]);
    setPurchasePayment('');
    setPurchaseBardhanRate(DEFAULT_BARDHAN_RATE.toString());
  };

  // Save sale record
  const handleSaveSale = () => {
    if (saleEntries.length === 0) {
      alert('Please add at least one entry');
      return;
    }

    const totalBags = saleEntries.reduce((sum, e) => sum + e.bags, 0);
    const totalWeightInQuintals = saleEntries.reduce((sum, e) => sum + e.weightInQuintals, 0);
    const entriesAmount = saleEntries.reduce((sum, e) => sum + e.totalAmount, 0);
    const amountReceived = parseFloat(salePayment) || 0;
    const bardhanRate = parseFloat(saleBardhanRate) || DEFAULT_BARDHAN_RATE;
    const bardhanAmount = totalBags * bardhanRate;
    const kantaRate = parseFloat(saleKantaRate) || DEFAULT_KANTA_RATE;
    const kantaAmount = totalBags * kantaRate;
    const totalAmount = entriesAmount + bardhanAmount + kantaAmount; // Include bardhan and kanta in total

    const newRecord: TradeRecord = {
      id: Date.now().toString(),
      traderName: saleTrader || 'Unknown Buyer',
      entries: [...saleEntries],
      totalBags,
      totalWeightInQuintals,
      totalAmount,
      amountPaid: 0,
      amountReceived,
      bardhanRate,
      bardhanAmount,
      kantaRate,
      kantaAmount
    };

    setSales([...sales, newRecord]);
    setSaleTrader('');
    setSaleEntries([]);
    setSalePayment('');
    setSaleBardhanRate(DEFAULT_BARDHAN_RATE.toString());
    setSaleKantaRate(DEFAULT_KANTA_RATE.toString());
  };

  // Delete records
  const handleDeletePurchase = (id: string) => {
    setPurchases(purchases.filter(p => p.id !== id));
  };

  const handleDeleteSale = (id: string) => {
    setSales(sales.filter(s => s.id !== id));
  };

  // Update payment for purchase record
  const handleUpdatePurchasePayment = (id: string, amount: number) => {
    setPurchases(purchases.map(p =>
      p.id === id ? { ...p, amountPaid: amount } : p
    ));
    setEditingPurchasePayment(null);
    setEditPurchaseAmount('');
  };

  // Update payment for sale record
  const handleUpdateSalePayment = (id: string, amount: number) => {
    setSales(sales.map(s =>
      s.id === id ? { ...s, amountReceived: amount } : s
    ));
    setEditingSalePayment(null);
    setEditSaleAmount('');
  };

  // Add payment to purchase record
  const handleAddPurchasePaymentAmount = (id: string, additionalAmount: number) => {
    setPurchases(purchases.map(p =>
      p.id === id ? { ...p, amountPaid: (p.amountPaid || 0) + additionalAmount } : p
    ));
    setEditingPurchasePayment(null);
    setEditPurchaseAmount('');
  };

  // Add payment to sale record
  const handleAddSalePaymentAmount = (id: string, additionalAmount: number) => {
    setSales(sales.map(s =>
      s.id === id ? { ...s, amountReceived: (s.amountReceived || 0) + additionalAmount } : s
    ));
    setEditingSalePayment(null);
    setEditSaleAmount('');
  };

  // Current totals
  const currentPurchaseBags = purchaseEntries.reduce((sum, e) => sum + e.bags, 0);
  const currentPurchaseWeight = purchaseEntries.reduce((sum, e) => sum + e.weightInQuintals, 0);
  const currentPurchaseAmount = purchaseEntries.reduce((sum, e) => sum + e.totalAmount, 0);

  const currentSaleBags = saleEntries.reduce((sum, e) => sum + e.bags, 0);
  const currentSaleWeight = saleEntries.reduce((sum, e) => sum + e.weightInQuintals, 0);
  const currentSaleAmount = saleEntries.reduce((sum, e) => sum + e.totalAmount, 0);

  // Overall totals
  const totalPurchaseAmount = purchases.reduce((sum, p) => sum + p.totalAmount, 0);
  const totalSaleAmount = sales.reduce((sum, s) => sum + s.totalAmount, 0);
  const netProfit = totalSaleAmount - totalPurchaseAmount;

  // Save session to Supabase
  const handleSaveSession = async () => {
    if (!user) {
      alert('Please login to save sessions');
      return;
    }

    if (purchases.length === 0 && sales.length === 0) {
      alert('Please add at least one purchase or sale before saving');
      return;
    }

    const name = sessionName || `Session ${new Date().toLocaleDateString()}`;
    setLoading(true);

    const sessionData = {
      user_id: user.id,
      session_name: name,
      total_purchase_amount: totalPurchaseAmount,
      total_sale_amount: totalSaleAmount,
      net_profit: netProfit,
      purchases: purchases,
      sales: sales
    };

    let error;

    if (currentSessionId) {
      // Update existing session
      const result = await supabase
        .from('trade_sessions')
        .update(sessionData)
        .eq('id', currentSessionId);
      error = result.error;
    } else {
      // Insert new session
      const result = await supabase
        .from('trade_sessions')
        .insert([sessionData]);
      error = result.error;
    }

    setLoading(false);

    if (error) {
      console.error('Error saving session:', error);
      alert('Error saving session. Please check if the table exists.');
    } else {
      alert(currentSessionId ? 'Session updated successfully!' : 'Session saved successfully!');
      handleResetAll();
      fetchSessions();
    }
  };

  // Delete session from Supabase
  const handleDeleteSession = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this session?')) return;

    const { error } = await supabase
      .from('trade_sessions')
      .delete()
      .eq('id', id);

    if (error) {
      console.error('Error deleting session:', error);
      alert('Error deleting session');
    } else {
      fetchSessions();
    }
  };

  // Load session
  const handleLoadSession = (session: DbTradeSession) => {
    // Add default values for new fields if they don't exist in old data
    const loadedPurchases = (session.purchases || []).map(p => ({
      ...p,
      amountPaid: p.amountPaid || 0,
      amountReceived: p.amountReceived || 0,
      bardhanRate: p.bardhanRate || DEFAULT_BARDHAN_RATE,
      bardhanAmount: p.bardhanAmount || 0
    }));
    const loadedSales = (session.sales || []).map(s => ({
      ...s,
      amountPaid: s.amountPaid || 0,
      amountReceived: s.amountReceived || 0,
      bardhanRate: s.bardhanRate || DEFAULT_BARDHAN_RATE,
      bardhanAmount: s.bardhanAmount || 0,
      kantaRate: s.kantaRate || DEFAULT_KANTA_RATE,
      kantaAmount: s.kantaAmount || 0
    }));
    setPurchases(loadedPurchases);
    setSales(loadedSales);
    setSessionName(session.session_name);
    setCurrentSessionId(session.id || null); // Track that we're editing an existing session
    setShowHistory(false);
  };

  const handleResetAll = () => {
    setPurchases([]);
    setSales([]);
    setPurchaseTrader('');
    setSaleTrader('');
    setPurchaseEntries([]);
    setSaleEntries([]);
    setPurchaseInput({ bags: '', weight: '', rate: '' });
    setSaleInput({ bags: '', weight: '', rate: '' });
    setSessionName('');
    setPurchasePayment('');
    setSalePayment('');
    setTraderSearch('');
    setEditingPurchasePayment(null);
    setEditPurchaseAmount('');
    setEditingSalePayment(null);
    setEditSaleAmount('');
    setCurrentSessionId(null); // Clear the current session ID to start fresh
    setPurchaseBardhanRate(DEFAULT_BARDHAN_RATE.toString());
    setSaleBardhanRate(DEFAULT_BARDHAN_RATE.toString());
    setSaleKantaRate(DEFAULT_KANTA_RATE.toString());
  };

  // Inventory tracking - bags purchased vs sold
  const totalBagsPurchased = purchases.reduce((sum, p) => sum + p.totalBags, 0);
  const totalBagsSold = sales.reduce((sum, s) => sum + s.totalBags, 0);
  const remainingBags = totalBagsPurchased - totalBagsSold;

  // Payment tracking
  const totalAmountToPay = purchases.reduce((sum, p) => sum + p.totalAmount, 0);
  const totalAmountPaid = purchases.reduce((sum, p) => sum + (p.amountPaid || 0), 0);
  const pendingPayment = totalAmountToPay - totalAmountPaid;

  const totalAmountToReceive = sales.reduce((sum, s) => sum + s.totalAmount, 0);
  const totalAmountReceived = sales.reduce((sum, s) => sum + (s.amountReceived || 0), 0);
  const pendingReceivable = totalAmountToReceive - totalAmountReceived;

  // Filter sessions by trader search
  const filteredSessions = traderSearch
    ? savedSessions.filter(session => {
        const searchLower = traderSearch.toLowerCase();
        const purchaseMatch = (session.purchases || []).some(p =>
          p.traderName.toLowerCase().includes(searchLower)
        );
        const saleMatch = (session.sales || []).some(s =>
          s.traderName.toLowerCase().includes(searchLower)
        );
        return purchaseMatch || saleMatch || session.session_name.toLowerCase().includes(searchLower);
      })
    : savedSessions;

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="App">
        <div className="loading-screen">
          <h1>🌶️ Loading...</h1>
        </div>
      </div>
    );
  }

  // Show login if not authenticated
  if (!user) {
    return <Auth onLogin={() => {}} />;
  }

  return (
    <div className="App">
      <div className="container">
        {/* Header with user info */}
        <div className="app-header">
          <h1>🌶️ Chilli Trade Tracker</h1>
          <div className="user-info">
            <span className="user-email">{user.email}</span>
            <button onClick={handleLogout} className="logout-btn">Logout</button>
          </div>
        </div>

        {/* Session Controls */}
        <div className="session-controls">
          <input
            type="text"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            placeholder="Session name (e.g., Jan 2024 Batch)"
            className="session-input"
          />
          <button onClick={handleSaveSession} className="save-session-btn" disabled={loading}>
            {loading ? 'Saving...' : '💾 Save Session'}
          </button>
          <button onClick={() => setShowHistory(!showHistory)} className="history-btn">
            📋 {showHistory ? 'Hide' : 'Show'} History ({savedSessions.length})
          </button>
        </div>

        {/* Session History */}
        {showHistory && (
          <div className="session-history">
            <h2>Saved Sessions</h2>
            <div className="search-box">
              <input
                type="text"
                value={traderSearch}
                onChange={(e) => setTraderSearch(e.target.value)}
                placeholder="Search by trader name or session..."
                className="search-input"
              />
              {traderSearch && (
                <button onClick={() => setTraderSearch('')} className="clear-search">×</button>
              )}
            </div>
            {filteredSessions.length === 0 ? (
              <p className="no-sessions">
                {traderSearch ? `No sessions found for "${traderSearch}"` : 'No saved sessions yet'}
              </p>
            ) : (
              <div className="session-list">
                {filteredSessions.map((session) => (
                  <div key={session.id} className="session-card">
                    <div className="session-header">
                      <span className="session-name">{session.session_name}</span>
                      <span className="session-date">
                        {new Date(session.created_at!).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="session-traders">
                      {(session.purchases || []).length > 0 && (
                        <span className="trader-tag purchase">
                          Sellers: {[...new Set((session.purchases || []).map(p => p.traderName))].join(', ')}
                        </span>
                      )}
                      {(session.sales || []).length > 0 && (
                        <span className="trader-tag sale">
                          Buyers: {[...new Set((session.sales || []).map(s => s.traderName))].join(', ')}
                        </span>
                      )}
                    </div>
                    <div className="session-details">
                      <span className="purchase">Purchase: ₹{session.total_purchase_amount.toFixed(2)}</span>
                      <span className="sale">Sale: ₹{session.total_sale_amount.toFixed(2)}</span>
                      <span className={session.net_profit >= 0 ? 'profit' : 'loss'}>
                        {session.net_profit >= 0 ? 'Profit' : 'Loss'}: ₹{Math.abs(session.net_profit).toFixed(2)}
                      </span>
                    </div>
                    <div className="session-actions">
                      <button onClick={() => handleLoadSession(session)} className="load-btn">Load</button>
                      <button onClick={() => handleDeleteSession(session.id!)} className="delete-session-btn">Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Summary Dashboard */}
        {(purchases.length > 0 || sales.length > 0) && (
          <div className="summary-dashboard">
            {/* Profit Summary */}
            <div className={`profit-summary ${netProfit >= 0 ? 'profit' : 'loss'}`}>
              <h2>Net Profit/Loss</h2>
              <div className="profit-details">
                <div className="profit-item">
                  <span>Total Purchase:</span>
                  <span className="amount purchase">₹{totalPurchaseAmount.toFixed(2)}</span>
                </div>
                <div className="profit-item">
                  <span>Total Sale:</span>
                  <span className="amount sale">₹{totalSaleAmount.toFixed(2)}</span>
                </div>
                <div className="profit-item net">
                  <span>Net {netProfit >= 0 ? 'Profit' : 'Loss'}:</span>
                  <span className={`amount ${netProfit >= 0 ? 'profit-text' : 'loss-text'}`}>
                    ₹{Math.abs(netProfit).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Inventory Tracking */}
            <div className="inventory-summary">
              <h2>Inventory Status</h2>
              <div className="inventory-details">
                <div className="inventory-item">
                  <span>Bags Purchased:</span>
                  <span className="bags-count purchase">{totalBagsPurchased}</span>
                </div>
                <div className="inventory-item">
                  <span>Bags Sold:</span>
                  <span className="bags-count sale">{totalBagsSold}</span>
                </div>
                <div className={`inventory-item remaining ${remainingBags > 0 ? 'positive' : remainingBags < 0 ? 'negative' : ''}`}>
                  <span>Remaining Bags:</span>
                  <span className="bags-count">{remainingBags}</span>
                </div>
              </div>
            </div>

            {/* Payment Tracking */}
            <div className="payment-summary">
              <h2>Payment Status</h2>
              <div className="payment-grid">
                <div className="payment-section payable">
                  <h3>To Pay (Sellers)</h3>
                  <div className="payment-item">
                    <span>Total Amount:</span>
                    <span>₹{totalAmountToPay.toFixed(2)}</span>
                  </div>
                  <div className="payment-item">
                    <span>Amount Paid:</span>
                    <span className="paid">₹{totalAmountPaid.toFixed(2)}</span>
                  </div>
                  <div className="payment-item pending">
                    <span>Pending:</span>
                    <span className="pending-amount">₹{pendingPayment.toFixed(2)}</span>
                  </div>
                </div>
                <div className="payment-section receivable">
                  <h3>To Receive (Buyers)</h3>
                  <div className="payment-item">
                    <span>Total Amount:</span>
                    <span>₹{totalAmountToReceive.toFixed(2)}</span>
                  </div>
                  <div className="payment-item">
                    <span>Amount Received:</span>
                    <span className="received">₹{totalAmountReceived.toFixed(2)}</span>
                  </div>
                  <div className="payment-item pending">
                    <span>Pending:</span>
                    <span className="pending-amount">₹{pendingReceivable.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="trade-sections">
          {/* Purchase Section */}
          <div className="trade-section purchase-section">
            <h2 className="section-title purchase">📥 Purchase (Buying)</h2>

            <div className="trader-section">
              <label>
                Seller Name:
                <input
                  type="text"
                  value={purchaseTrader}
                  onChange={(e) => setPurchaseTrader(e.target.value)}
                  placeholder="Enter seller name"
                />
              </label>
            </div>

            {/* Add Entry Form */}
            <div className="entry-form">
              <h3>Add Entry</h3>
              <div className="form-row">
                <label>
                  Bags:
                  <input
                    type="number"
                    value={purchaseInput.bags}
                    onChange={(e) => setPurchaseInput({...purchaseInput, bags: e.target.value})}
                    placeholder="10"
                    step="1"
                  />
                </label>
                <label>
                  Weight:
                  <input
                    type="number"
                    value={purchaseInput.weight}
                    onChange={(e) => setPurchaseInput({...purchaseInput, weight: e.target.value})}
                    placeholder="528.5"
                    step="0.1"
                  />
                  <small className="weight-hint">528.5 = 5Q + 28.5Kg</small>
                </label>
                <label>
                  Rate/Q (₹):
                  <input
                    type="number"
                    value={purchaseInput.rate}
                    onChange={(e) => setPurchaseInput({...purchaseInput, rate: e.target.value})}
                    placeholder="5000"
                    step="0.01"
                  />
                </label>
                <button onClick={handleAddPurchaseEntry} className="add-entry-btn">+ Add</button>
              </div>
            </div>

            {/* Current Entries Table */}
            {purchaseEntries.length > 0 && (
              <div className="entries-table current-entries">
                <table>
                  <thead>
                    <tr>
                      <th>S.No</th>
                      <th>Bags</th>
                      <th>Weight</th>
                      <th>Weight (Q)</th>
                      <th>Rate (₹)</th>
                      <th>Amount (₹)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {purchaseEntries.map((entry, index) => (
                      <tr key={entry.id}>
                        <td>{index + 1}</td>
                        <td>{entry.bags}</td>
                        <td>{entry.weight}</td>
                        <td>{entry.weightInQuintals.toFixed(3)}</td>
                        <td>{entry.ratePerQuintal.toFixed(2)}</td>
                        <td>{entry.totalAmount.toFixed(2)}</td>
                        <td>
                          <button onClick={() => handleDeletePurchaseEntry(entry.id)} className="delete-btn small">
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="total-row">
                      <td><strong>TOTAL</strong></td>
                      <td><strong>{currentPurchaseBags}</strong></td>
                      <td></td>
                      <td><strong>{currentPurchaseWeight.toFixed(3)}</strong></td>
                      <td></td>
                      <td><strong>₹{currentPurchaseAmount.toFixed(2)}</strong></td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>

                {/* Payment Input */}
                <div className="payment-input-section">
                  <label>
                    Amount Paid to Seller (₹):
                    <input
                      type="number"
                      value={purchasePayment}
                      onChange={(e) => setPurchasePayment(e.target.value)}
                      placeholder="0"
                      step="0.01"
                    />
                  </label>
                  <span className="payment-hint">
                    Total: ₹{currentPurchaseAmount.toFixed(2)} |
                    Pending: ₹{(currentPurchaseAmount - (parseFloat(purchasePayment) || 0)).toFixed(2)}
                  </span>
                </div>

                <button onClick={handleSavePurchase} className="save-btn purchase-btn">
                  Save Purchase
                </button>
              </div>
            )}

            {/* Saved Purchase Records */}
            {purchases.length > 0 && (
              <div className="saved-records">
                <h3>Saved Purchases</h3>
                {purchases.map((record) => (
                  <div key={record.id} className="record-card">
                    <div className="record-header">
                      <span className="trader-name">{record.traderName}</span>
                      <button onClick={() => handleDeletePurchase(record.id)} className="delete-btn small">×</button>
                    </div>
                    <div className="record-details">
                      <span>Bags: {record.totalBags}</span>
                      <span>Weight: {record.totalWeightInQuintals.toFixed(3)} Q</span>
                      <span className="record-amount">₹{record.totalAmount.toFixed(2)}</span>
                    </div>
                    <div className="record-payment">
                      <span className="paid">Paid: ₹{(record.amountPaid || 0).toFixed(2)}</span>
                      <span className={`pending ${(record.totalAmount - (record.amountPaid || 0)) > 0 ? 'has-pending' : ''}`}>
                        Pending: ₹{(record.totalAmount - (record.amountPaid || 0)).toFixed(2)}
                      </span>
                    </div>
                    {/* Editable Payment Section */}
                    {editingPurchasePayment === record.id ? (
                      <div className="edit-payment-section">
                        <input
                          type="number"
                          value={editPurchaseAmount}
                          onChange={(e) => setEditPurchaseAmount(e.target.value)}
                          placeholder="Enter amount"
                          step="0.01"
                          autoFocus
                        />
                        <div className="edit-payment-actions">
                          <button
                            onClick={() => handleAddPurchasePaymentAmount(record.id, parseFloat(editPurchaseAmount) || 0)}
                            className="add-payment-btn"
                          >
                            + Add
                          </button>
                          <button
                            onClick={() => handleUpdatePurchasePayment(record.id, parseFloat(editPurchaseAmount) || 0)}
                            className="set-payment-btn"
                          >
                            Set Total
                          </button>
                          <button
                            onClick={() => { setEditingPurchasePayment(null); setEditPurchaseAmount(''); }}
                            className="cancel-payment-btn"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditingPurchasePayment(record.id); setEditPurchaseAmount(''); }}
                        className="edit-payment-btn"
                      >
                        💰 Update Payment
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sale Section */}
          <div className="trade-section sale-section">
            <h2 className="section-title sale">📤 Sale (Selling)</h2>

            <div className="trader-section">
              <label>
                Buyer Name:
                <input
                  type="text"
                  value={saleTrader}
                  onChange={(e) => setSaleTrader(e.target.value)}
                  placeholder="Enter buyer name"
                />
              </label>
            </div>

            {/* Add Entry Form */}
            <div className="entry-form">
              <h3>Add Entry</h3>
              <div className="form-row">
                <label>
                  Bags:
                  <input
                    type="number"
                    value={saleInput.bags}
                    onChange={(e) => setSaleInput({...saleInput, bags: e.target.value})}
                    placeholder="10"
                    step="1"
                  />
                </label>
                <label>
                  Weight:
                  <input
                    type="number"
                    value={saleInput.weight}
                    onChange={(e) => setSaleInput({...saleInput, weight: e.target.value})}
                    placeholder="528.5"
                    step="0.1"
                  />
                  <small className="weight-hint">528.5 = 5Q + 28.5Kg</small>
                </label>
                <label>
                  Rate/Q (₹):
                  <input
                    type="number"
                    value={saleInput.rate}
                    onChange={(e) => setSaleInput({...saleInput, rate: e.target.value})}
                    placeholder="5500"
                    step="0.01"
                  />
                </label>
                <button onClick={handleAddSaleEntry} className="add-entry-btn sale">+ Add</button>
              </div>
            </div>

            {/* Current Entries Table */}
            {saleEntries.length > 0 && (
              <div className="entries-table current-entries">
                <table>
                  <thead>
                    <tr>
                      <th>S.No</th>
                      <th>Bags</th>
                      <th>Weight</th>
                      <th>Weight (Q)</th>
                      <th>Rate (₹)</th>
                      <th>Amount (₹)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {saleEntries.map((entry, index) => (
                      <tr key={entry.id}>
                        <td>{index + 1}</td>
                        <td>{entry.bags}</td>
                        <td>{entry.weight}</td>
                        <td>{entry.weightInQuintals.toFixed(3)}</td>
                        <td>{entry.ratePerQuintal.toFixed(2)}</td>
                        <td>{entry.totalAmount.toFixed(2)}</td>
                        <td>
                          <button onClick={() => handleDeleteSaleEntry(entry.id)} className="delete-btn small">
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="total-row">
                      <td><strong>TOTAL</strong></td>
                      <td><strong>{currentSaleBags}</strong></td>
                      <td></td>
                      <td><strong>{currentSaleWeight.toFixed(3)}</strong></td>
                      <td></td>
                      <td><strong>₹{currentSaleAmount.toFixed(2)}</strong></td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>

                {/* Payment Input */}
                <div className="payment-input-section">
                  <label>
                    Amount Received from Buyer (₹):
                    <input
                      type="number"
                      value={salePayment}
                      onChange={(e) => setSalePayment(e.target.value)}
                      placeholder="0"
                      step="0.01"
                    />
                  </label>
                  <span className="payment-hint">
                    Total: ₹{currentSaleAmount.toFixed(2)} |
                    Pending: ₹{(currentSaleAmount - (parseFloat(salePayment) || 0)).toFixed(2)}
                  </span>
                </div>

                <button onClick={handleSaveSale} className="save-btn sale-btn">
                  Save Sale
                </button>
              </div>
            )}

            {/* Saved Sale Records */}
            {sales.length > 0 && (
              <div className="saved-records">
                <h3>Saved Sales</h3>
                {sales.map((record) => (
                  <div key={record.id} className="record-card sale">
                    <div className="record-header">
                      <span className="trader-name">{record.traderName}</span>
                      <button onClick={() => handleDeleteSale(record.id)} className="delete-btn small">×</button>
                    </div>
                    <div className="record-details">
                      <span>Bags: {record.totalBags}</span>
                      <span>Weight: {record.totalWeightInQuintals.toFixed(3)} Q</span>
                      <span className="record-amount">₹{record.totalAmount.toFixed(2)}</span>
                    </div>
                    <div className="record-payment">
                      <span className="received">Received: ₹{(record.amountReceived || 0).toFixed(2)}</span>
                      <span className={`pending ${(record.totalAmount - (record.amountReceived || 0)) > 0 ? 'has-pending' : ''}`}>
                        Pending: ₹{(record.totalAmount - (record.amountReceived || 0)).toFixed(2)}
                      </span>
                    </div>
                    {/* Editable Payment Section */}
                    {editingSalePayment === record.id ? (
                      <div className="edit-payment-section">
                        <input
                          type="number"
                          value={editSaleAmount}
                          onChange={(e) => setEditSaleAmount(e.target.value)}
                          placeholder="Enter amount"
                          step="0.01"
                          autoFocus
                        />
                        <div className="edit-payment-actions">
                          <button
                            onClick={() => handleAddSalePaymentAmount(record.id, parseFloat(editSaleAmount) || 0)}
                            className="add-payment-btn"
                          >
                            + Add
                          </button>
                          <button
                            onClick={() => handleUpdateSalePayment(record.id, parseFloat(editSaleAmount) || 0)}
                            className="set-payment-btn"
                          >
                            Set Total
                          </button>
                          <button
                            onClick={() => { setEditingSalePayment(null); setEditSaleAmount(''); }}
                            className="cancel-payment-btn"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditingSalePayment(record.id); setEditSaleAmount(''); }}
                        className="edit-payment-btn sale"
                      >
                        💰 Update Payment
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {(purchases.length > 0 || sales.length > 0) && (
          <button onClick={handleResetAll} className="reset-btn">Reset All</button>
        )}
      </div>
    </div>
  );
}

export default App;
