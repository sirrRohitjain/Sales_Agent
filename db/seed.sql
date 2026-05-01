-- ═══════════════════════════════════════════════════════════════
-- seed.sql
-- Inserts 50 realistic dummy leads with varied profiles.
-- Covers: different incomes, employment types, credit scores,
--         cities, and priority scores.
--
-- How to run:
--   psql -U postgres -d credit_card_agent_db -f seed.sql
-- ═══════════════════════════════════════════════════════════════

-- Clear existing seed data (safe to re-run)
TRUNCATE leads RESTART IDENTITY CASCADE;

INSERT INTO leads (name, phone, age, income, credit_score, employment_type, city, state, language, status, priority_score, source)
VALUES

-- ── HIGH PRIORITY — Salaried, good income, good score ────────────
('Rahul Sharma',      '9876543210', 28, 65000,  740, 'salaried',      'Mumbai',    'Maharashtra', 'english',  'pending', 95, 'csv_import'),
('Priya Patel',       '9845123456', 30, 72000,  760, 'salaried',      'Bangalore', 'Karnataka',   'english',  'pending', 93, 'csv_import'),
('Amit Verma',        '9812345678', 32, 80000,  750, 'salaried',      'Delhi',     'Delhi',       'hindi',    'pending', 92, 'csv_import'),
('Sneha Nair',        '9723456789', 27, 58000,  720, 'salaried',      'Chennai',   'Tamil Nadu',  'english',  'pending', 90, 'csv_import'),
('Vikram Singh',      '9634567890', 35, 95000,  770, 'salaried',      'Pune',      'Maharashtra', 'english',  'pending', 90, 'csv_import'),
('Ananya Das',        '9745678901', 29, 62000,  730, 'salaried',      'Kolkata',   'West Bengal', 'english',  'pending', 88, 'csv_import'),
('Rohan Mehta',       '9856789012', 31, 75000,  755, 'salaried',      'Hyderabad', 'Telangana',   'english',  'pending', 88, 'csv_import'),
('Kavya Reddy',       '9967890123', 26, 55000,  715, 'salaried',      'Bangalore', 'Karnataka',   'english',  'pending', 85, 'csv_import'),
('Arjun Iyer',        '9078901234', 33, 88000,  765, 'salaried',      'Chennai',   'Tamil Nadu',  'english',  'pending', 85, 'csv_import'),
('Pooja Gupta',       '9189012345', 28, 48000,  700, 'salaried',      'Jaipur',    'Rajasthan',   'hindi',    'pending', 82, 'csv_import'),

-- ── HIGH PRIORITY — Business / Self-employed ─────────────────────
('Suresh Kumar',      '9290123456', 40, 120000, 780, 'business',      'Mumbai',    'Maharashtra', 'hindi',    'pending', 95, 'csv_import'),
('Meena Agarwal',     '9301234567', 37, 100000, 760, 'business',      'Delhi',     'Delhi',       'hindi',    'pending', 93, 'csv_import'),
('Rajesh Joshi',      '9412345678', 42, 90000,  750, 'self_employed', 'Pune',      'Maharashtra', 'hindi',    'pending', 88, 'csv_import'),
('Lakshmi Venkat',    '9523456789', 38, 85000,  745, 'business',      'Hyderabad', 'Telangana',   'english',  'pending', 87, 'csv_import'),
('Deepak Malhotra',   '9634567891', 44, 110000, 775, 'business',      'Chandigarh','Punjab',      'hindi',    'pending', 87, 'csv_import'),
('Sunita Rao',        '9745678902', 36, 78000,  738, 'self_employed', 'Bangalore', 'Karnataka',   'english',  'pending', 84, 'csv_import'),
('Harish Tiwari',     '9856789013', 45, 95000,  758, 'business',      'Lucknow',   'Uttar Pradesh','hindi',   'pending', 83, 'csv_import'),
('Nandini Pillai',    '9967890124', 34, 68000,  725, 'self_employed', 'Kochi',     'Kerala',      'english',  'pending', 80, 'csv_import'),

-- ── MEDIUM PRIORITY — Moderate income ────────────────────────────
('Sanjay Bhatt',      '9078901235', 29, 38000,  690, 'salaried',      'Ahmedabad', 'Gujarat',     'hindi',    'pending', 72, 'csv_import'),
('Ritu Sharma',       '9189012346', 25, 32000,  670, 'salaried',      'Bhopal',    'Madhya Pradesh','hindi',  'pending', 70, 'csv_import'),
('Arun Nambiar',      '9290123457', 27, 42000,  695, 'salaried',      'Kochi',     'Kerala',      'english',  'pending', 70, 'csv_import'),
('Divya Saxena',      '9301234568', 30, 35000,  680, 'salaried',      'Agra',      'Uttar Pradesh','hindi',   'pending', 68, 'csv_import'),
('Manoj Yadav',       '9412345679', 33, 45000,  700, 'salaried',      'Patna',     'Bihar',       'hindi',    'pending', 68, 'csv_import'),
('Swati Kulkarni',    '9523456790', 28, 40000,  685, 'salaried',      'Nagpur',    'Maharashtra', 'hindi',    'pending', 65, 'csv_import'),
('Prakash Naidu',     '9634567892', 31, 36000,  675, 'salaried',      'Vizag',     'Andhra Pradesh','english','pending', 65, 'csv_import'),
('Asha Krishnan',     '9745678903', 26, 33000,  668, 'salaried',      'Coimbatore','Tamil Nadu',  'english',  'pending', 63, 'csv_import'),
('Nitesh Pandey',     '9856789014', 29, 28000,  660, 'salaried',      'Varanasi',  'Uttar Pradesh','hindi',   'pending', 60, 'csv_import'),
('Geeta Mishra',      '9967890125', 32, 30000,  655, 'salaried',      'Indore',    'Madhya Pradesh','hindi',  'pending', 60, 'csv_import'),

-- ── MEDIUM PRIORITY — Freelancers / Self-employed ────────────────
('Karan Kapoor',      '9078901236', 26, 35000,  665, 'self_employed', 'Mumbai',    'Maharashtra', 'english',  'pending', 65, 'csv_import'),
('Tanvi Bose',        '9189012347', 28, 40000,  680, 'self_employed', 'Kolkata',   'West Bengal', 'english',  'pending', 63, 'csv_import'),
('Nikhil Shetty',     '9290123458', 30, 45000,  690, 'self_employed', 'Mangalore', 'Karnataka',   'english',  'pending', 62, 'csv_import'),
('Pallavi Desai',     '9301234569', 27, 38000,  672, 'freelancer',    'Pune',      'Maharashtra', 'english',  'pending', 60, 'csv_import'),
('Siddharth Jain',    '9412345680', 32, 52000,  705, 'self_employed', 'Rajkot',    'Gujarat',     'hindi',    'pending', 60, 'csv_import'),

-- ── LOWER PRIORITY — Lower income / needs follow-up ──────────────
('Mohan Lal',         '9523456791', 45, 22000,  640, 'salaried',      'Meerut',    'Uttar Pradesh','hindi',   'pending', 45, 'csv_import'),
('Sundar Pichai',     '9634567893', 38, 18000,  630, 'salaried',      'Trichy',    'Tamil Nadu',  'english',  'pending', 42, 'csv_import'),
('Kamala Devi',       '9745678904', 42, 20000,  625, 'salaried',      'Mysore',    'Karnataka',   'english',  'pending', 40, 'csv_import'),
('Brij Mohan',        '9856789015', 50, 25000,  645, 'salaried',      'Jodhpur',   'Rajasthan',   'hindi',    'pending', 40, 'csv_import'),
('Sarita Singh',      '9967890126', 35, 19000,  635, 'salaried',      'Ranchi',    'Jharkhand',   'hindi',    'pending', 38, 'csv_import'),

-- ── RETRY LEADS — Previously not answered ────────────────────────
('Ashok Meena',       '9078901237', 29, 55000,  710, 'salaried',      'Jaipur',    'Rajasthan',   'hindi',    'retry',   75, 'csv_import'),
('Bhavna Shah',       '9189012348', 31, 62000,  725, 'business',      'Surat',     'Gujarat',     'hindi',    'retry',   73, 'csv_import'),
('Chirag Patel',      '9290123459', 27, 48000,  695, 'salaried',      'Vadodara',  'Gujarat',     'hindi',    'retry',   70, 'csv_import'),
('Deepika Menon',     '9301234570', 33, 70000,  740, 'salaried',      'Trivandrum','Kerala',      'english',  'retry',   70, 'csv_import'),
('Esha Tomar',        '9412345681', 26, 36000,  668, 'salaried',      'Gurgaon',   'Haryana',     'hindi',    'retry',   65, 'csv_import'),

-- ── ALREADY CALLED — Various outcomes ────────────────────────────
('Farhan Akhtar',     '9523456792', 30, 75000,  745, 'salaried',      'Mumbai',    'Maharashtra', 'english',  'applied',          85, 'csv_import'),
('Gita Bhatia',       '9634567894', 34, 60000,  720, 'salaried',      'Delhi',     'Delhi',       'hindi',    'not_interested',    70, 'csv_import'),
('Hemant Trivedi',    '9745678905', 29, 58000,  715, 'self_employed', 'Ahmedabad', 'Gujarat',     'hindi',    'applied',          80, 'csv_import'),
('Isha Malviya',      '9856789016', 25, 30000,  660, 'salaried',      'Bhopal',    'Madhya Pradesh','hindi',  'not_interested',    55, 'csv_import'),
('Jayesh Thakkar',    '9967890127', 37, 85000,  755, 'business',      'Surat',     'Gujarat',     'hindi',    'applied',          88, 'csv_import'),
('Kavitha Nair',      '9078901238', 32, 45000,  688, 'salaried',      'Kochi',     'Kerala',      'english',  'called',           68, 'csv_import');


-- ═══════════════════════════════════════════════════════════════
-- VERIFY: Show summary of seeded leads
-- ═══════════════════════════════════════════════════════════════
SELECT
    status,
    COUNT(*)              AS total,
    ROUND(AVG(income))    AS avg_income,
    ROUND(AVG(credit_score)) AS avg_credit_score
FROM leads
GROUP BY status
ORDER BY total DESC;
