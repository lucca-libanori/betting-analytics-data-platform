-- Drop table
DROP TABLE IF EXISTS bets;

-- Create table
CREATE TABLE bets (
    bet_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    sport VARCHAR(50) NOT NULL,
    match VARCHAR(100) NOT NULL,
    selection VARCHAR(100) NOT NULL,
    tag VARCHAR(50),
    status VARCHAR(10) NOT NULL CHECK (status IN ('win', 'loss', 'void')),
    closing_odds FLOAT,
    odds FLOAT NOT NULL CHECK (odds > 1),
    stake FLOAT NOT NULL CHECK (stake > 0),
    profit FLOAT,
    sportsbook VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_bets_sport ON bets(sport);
CREATE INDEX idx_bets_sportsbook ON bets(sportsbook);
CREATE INDEX idx_bets_date ON bets(date);