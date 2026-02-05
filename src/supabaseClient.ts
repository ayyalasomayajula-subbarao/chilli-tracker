import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://fokfznfepgdvqgfopqir.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZva2Z6bmZlcGdkdnFnZm9wcWlyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAxMjUwMTIsImV4cCI6MjA4NTcwMTAxMn0.ruTx9KWUu9RlNbIo2JZPkG0CR7zX_-CE6kFJ0Lo3X3g';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Database types
export interface DbTradeSession {
  id?: string;
  created_at?: string;
  user_id?: string;
  session_name: string;
  total_purchase_amount: number;
  total_sale_amount: number;
  net_profit: number;
  purchases: DbTradeRecord[];
  sales: DbTradeRecord[];
}

export interface DbTradeRecord {
  id: string;
  traderName: string;
  entries: DbChilliEntry[];
  totalBags: number;
  totalWeightInQuintals: number;
  totalAmount: number;
  amountPaid?: number;
  amountReceived?: number;
  bardhanRate?: number; // Bardhan charge per bag (default ₹28)
  bardhanAmount?: number; // totalBags × bardhanRate
  kantaRate?: number; // Kanta charge per bag (default ₹7.5, only for sales)
  kantaAmount?: number; // totalBags × kantaRate (only for sales)
}

export interface DbChilliEntry {
  id: string;
  bags: number;
  weight: number;
  weightInQuintals: number;
  ratePerQuintal: number;
  totalAmount: number;
}
