-- Migration: Create trade_sessions table with user authentication
-- Run this SQL in your Supabase SQL Editor (Dashboard > SQL Editor)

-- Create the trade_sessions table
CREATE TABLE IF NOT EXISTS trade_sessions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  session_name TEXT NOT NULL,
  total_purchase_amount NUMERIC DEFAULT 0,
  total_sale_amount NUMERIC DEFAULT 0,
  net_profit NUMERIC DEFAULT 0,
  purchases JSONB DEFAULT '[]'::jsonb,
  sales JSONB DEFAULT '[]'::jsonb
);

-- Create index for faster user-based queries
CREATE INDEX IF NOT EXISTS idx_trade_sessions_user_id ON trade_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_sessions_created_at ON trade_sessions(created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE trade_sessions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only view their own sessions
CREATE POLICY "Users can view own sessions"
  ON trade_sessions
  FOR SELECT
  USING (auth.uid() = user_id);

-- Policy: Users can insert their own sessions
CREATE POLICY "Users can insert own sessions"
  ON trade_sessions
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own sessions
CREATE POLICY "Users can update own sessions"
  ON trade_sessions
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Policy: Users can delete their own sessions
CREATE POLICY "Users can delete own sessions"
  ON trade_sessions
  FOR DELETE
  USING (auth.uid() = user_id);

-- Enable realtime for the table (optional, for live updates)
ALTER PUBLICATION supabase_realtime ADD TABLE trade_sessions;
