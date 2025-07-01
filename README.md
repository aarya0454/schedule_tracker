# Daily Check-in App - Intelligent Self-Tracking Platform

A comprehensive Flask-based application for daily morning and evening check-ins with intelligent insights, habit tracking, and behavioral analysis.

## ✨ Features

### 🌅 Morning Check-ins
- **Sleep tracking**: Hours slept and sleep quality (1-5 scale)
- **Energy assessment**: Morning energy level (1-5 scale)
- **Goal setting**: Set one main goal for the day
- **Anxiety check**: Optional space to share concerns

### 🌙 Evening Check-ins
- **Goal review**: Did you accomplish your morning goal?
- **Mood rating**: Overall mood for the day (1-5 scale)
- **Exercise tracking**: Did you exercise today?
- **Energy drainers**: What drained your energy today?
- **Gratitude journal**: What are you grateful for?
- **Day win assessment**: Would you call today a win?
- **Overall day rating**: Emoji-based day rating (😀 😐 😞)

### 📊 Advanced Analytics & Insights
- **Trend visualizations**: Sleep vs energy, mood trends, exercise frequency
- **Goal accomplishment tracking**: Success rate and patterns
- **Habit analysis**: Top habits and frequency tracking
- **AI-powered insights**: Pattern detection and recommendations
- **Calendar heatmap**: Visual day win/loss tracking

### 🏷️ Habit Tag System
- **Custom habit tracking**: #coding, #gym, #reading, #meditation, etc.
- **Habit streaks**: Track consistency over time
- **Habit insights**: Most used habits and recommendations

### 🔔 Smart Reminders
- **Automated scheduling**: Morning (9 AM) and evening (9 PM) reminders
- **Reminder links**: Quick access via `/reminder/morning` or `/reminder/evening`
- **Email integration ready**: Easy to add email notifications

### 📈 Export & Data Management
- **CSV export**: Complete data export with all fields
- **JSON export**: Structured data for analysis
- **Edit functionality**: Update any past check-in
- **Data visualization**: Charts and graphs for insights

### 🎨 Modern UI/UX
- **Responsive design**: Works on mobile and desktop
- **Bootstrap 5**: Modern, clean interface
- **Dynamic forms**: Different questions for morning/evening
- **Motivational quotes**: Daily inspiration from API
- **Dark/light mode ready**: Easy theme switching

## 🚀 Installation

### Prerequisites
- Python 3.8+
- pip (Python package installer)

### Setup Instructions

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd Schedule
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**
   ```bash
   python migrate_db.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the app**
   - Open your browser and go to `http://localhost:5000`
   - Register a new account or use the test account:
     - Username: `testuser`
     - Password: `password123`

### Optional: Create Sample Data
```bash
python migrate_db.py --sample
```

## 📱 Usage Guide

### First Time Setup
1. **Register an account** with your email and password
2. **Log in** to access your personalized dashboard
3. **Submit your first check-in** (morning or evening)

### Daily Routine

#### Morning Check-in (5 AM - 12 PM)
1. Navigate to "Submit Check-in"
2. Select "Morning" (auto-detected based on time)
3. Answer the morning questions:
   - How many hours did you sleep?
   - How was your sleep quality?
   - What's your energy level?
   - What's one goal for today?
   - Any anxiety or concerns?

#### Evening Check-in (12 PM - 5 AM)
1. Navigate to "Submit Check-in"
2. Select "Evening" (auto-detected based on time)
3. Answer the evening questions:
   - Did you accomplish your goal?
   - How was your mood today?
   - Did you exercise?
   - What drained your energy?
   - What are you grateful for?
   - Was today a win?

### Dashboard Features
- **Today's Status**: Quick view of morning/evening completion
- **Insights**: AI-generated recommendations based on your patterns
- **Charts**: Visual trends of sleep, energy, mood, and goals
- **Habit Analysis**: Your most common habits and streaks
- **Calendar Heatmap**: Visual day win/loss tracking

### Data Management
- **Edit Check-ins**: Click "Edit" on any check-in to modify it
- **Export Data**: Download your data as CSV or JSON
- **Analytics**: Detailed analysis and insights

## 🏗️ Technical Architecture

### Database Schema
```sql
-- Users table
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(120) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Check-ins table (supports morning/evening)
CREATE TABLE checkin (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    time_of_day VARCHAR(10) NOT NULL, -- 'morning' or 'evening'
    
    -- Morning fields
    sleep_hours FLOAT,
    sleep_quality INTEGER,
    energy_level INTEGER,
    morning_goal TEXT,
    anxiety_level TEXT,
    
    -- Evening fields
    goal_accomplished BOOLEAN,
    mood_rating INTEGER,
    exercise_done BOOLEAN,
    what_drained_you TEXT,
    gratitude TEXT,
    day_win BOOLEAN,
    overall_day_rating VARCHAR(10),
    
    -- Legacy fields (backward compatibility)
    mood VARCHAR(20),
    focus_level INTEGER,
    tasks_done TEXT,
    diet TEXT,
    exercise TEXT,
    habits TEXT, -- JSON string
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Key Technologies
- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Database**: SQLite (easily switchable to PostgreSQL)
- **Scheduling**: APScheduler for reminders
- **Analytics**: NLTK for keyword analysis
- **Charts**: Chart.js for visualizations
- **UI**: Bootstrap 5, FontAwesome icons
- **APIs**: Motivational quotes from quotable.io

### File Structure
```
Schedule/
├── app.py                 # Main Flask application
├── migrate_db.py          # Database migration script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # Jinja2 templates
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   ├── submit.html       # Check-in form
│   ├── dashboard.html    # Main dashboard
│   ├── analytics.html    # Detailed analytics
│   └── edit_checkin.html # Edit check-in form
└── instance/             # Database files (auto-created)
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file for production settings:
```env
SECRET_KEY=your-super-secret-key-here
DATABASE_URL=postgresql://user:pass@localhost/dbname
FLASK_ENV=production
```

### Database Configuration
The app uses SQLite by default. For PostgreSQL:
1. Install `psycopg2-binary`
2. Update `SQLALCHEMY_DATABASE_URI` in `app.py`
3. Run migrations

### Reminder Configuration
Reminders are scheduled for:
- **Morning**: 9:00 AM daily
- **Evening**: 9:00 PM daily

To customize times, edit the `schedule_reminders()` function in `app.py`.

## 🚀 Deployment

### Local Development
```bash
export FLASK_ENV=development
python app.py
```

### Production Deployment
1. **Set up a production server** (e.g., Ubuntu with Nginx)
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install gunicorn
   ```
3. **Configure environment variables**
4. **Run with Gunicorn**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```
5. **Set up Nginx reverse proxy**
6. **Configure SSL certificates**

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 🔍 API Endpoints

### Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - User registration
- `GET /logout` - User logout

### Check-ins
- `GET/POST /submit` - Submit new check-in
- `GET/POST /edit/<date>/<time>` - Edit existing check-in
- `GET /dashboard` - Main dashboard view
- `GET /analytics` - Detailed analytics

### Data Export
- `GET /export/csv` - Export data as CSV
- `GET /export/json` - Export data as JSON

### Reminders
- `GET /reminder/morning` - Morning reminder link
- `GET /reminder/evening` - Evening reminder link

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

**Database errors**: Run `python migrate_db.py` to reset the database

**Port already in use**: Change the port in `app.py` or kill the existing process

**Missing dependencies**: Ensure you're in the virtual environment and run `pip install -r requirements.txt`

### Getting Help
- Check the logs in the terminal for error messages
- Ensure all dependencies are installed
. Verify the database is properly initialized

## 🎯 Roadmap

### Planned Features
- [ ] Email notifications for reminders
- [ ] Mobile app (React Native)
- [ ] Advanced analytics with machine learning
- [ ] Social features (share insights with friends)
- [ ] Integration with health apps (Apple Health, Google Fit)
- [ ] Custom habit creation
- [ ] Goal templates and suggestions
- [ ] Weekly/monthly reports
- [ ] Dark mode toggle
- [ ] Multi-language support

### Performance Improvements
- [ ] Database indexing optimization
- [ ] Caching for frequently accessed data
- [ ] API rate limiting
- [ ] Background task processing

---

**Built with ❤️ for better self-awareness and personal growth** 