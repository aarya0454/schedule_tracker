#!/usr/bin/env python3
"""
Database Migration Script for Daily Check-in App
This script migrates the database from the old single check-in model to the new morning/evening model.
"""

import os
import sys
from datetime import datetime, date, timedelta
import json
from sqlalchemy import inspect

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, CheckIn, Task

def migrate_database():
    """Migrate the database to the new schema"""
    with app.app_context():
        print("Starting database migration...")
        
        # Check if we need to migrate
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'checkin' not in existing_tables:
            print("No existing checkin table found. Creating new tables...")
            db.create_all()
            print("✅ Database tables created successfully!")
            return
        
        # Check if time_of_day column exists
        existing_columns = [col['name'] for col in inspector.get_columns('checkin')]
        
        if 'time_of_day' in existing_columns:
            print("✅ Database already migrated. No action needed.")
            return
        
        print("🔄 Migrating existing data to new schema...")
        
        # Get all existing check-ins
        old_checkins = db.session.execute(
            db.text("SELECT * FROM checkin")
        ).fetchall()
        
        print(f"Found {len(old_checkins)} existing check-ins to migrate...")
        
        # Create new table with updated schema
        db.drop_all()
        db.create_all()
        
        # Migrate existing data
        migrated_count = 0
        for old_checkin in old_checkins:
            try:
                # Create morning check-in
                morning_checkin = CheckIn(
                    user_id=old_checkin.user_id,
                    date=old_checkin.date,
                    time_of_day='morning',
                    sleep_hours=old_checkin.sleep_hours,
                    energy_level=old_checkin.energy_level,
                    focus_level=old_checkin.focus_level,
                    mood=old_checkin.mood,
                    tasks_done=old_checkin.tasks_done,
                    diet=old_checkin.diet,
                    exercise=old_checkin.exercise,
                    gratitude=old_checkin.gratitude,
                    habits=old_checkin.habits,
                    created_at=old_checkin.created_at
                )
                db.session.add(morning_checkin)
                
                # Create evening check-in with derived data
                evening_checkin = CheckIn(
                    user_id=old_checkin.user_id,
                    date=old_checkin.date,
                    time_of_day='evening',
                    mood_rating=convert_mood_to_rating(old_checkin.mood),
                    day_win=determine_day_win(old_checkin),
                    overall_day_rating=determine_overall_rating(old_checkin),
                    gratitude=old_checkin.gratitude,
                    habits=old_checkin.habits,
                    created_at=old_checkin.created_at
                )
                db.session.add(evening_checkin)
                
                migrated_count += 1
                
            except Exception as e:
                print(f"❌ Error migrating check-in {old_checkin.id}: {e}")
                db.session.rollback()
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"✅ Successfully migrated {migrated_count} check-ins!")
            print("✅ Database migration completed successfully!")
        except Exception as e:
            print(f"❌ Error committing migration: {e}")
            db.session.rollback()

        # After db.create_all(), print confirmation for Task table
        if not Task.__table__.exists(bind=db.engine):
            Task.__table__.create(bind=db.engine)
            print('✅ Task table created successfully!')
        else:
            print('Task table already exists.')

        # Add category column to Task table if it doesn't exist
        if 'category' not in [col['name'] for col in inspect(db.engine).get_columns('task')]:
            with db.engine.connect() as conn:
                conn.execute('ALTER TABLE task ADD COLUMN category VARCHAR(50) DEFAULT "General"')
            print('✅ Task.category column added.')
        else:
            print('Task.category column already exists.')

        # Add priority column to Task table if it doesn't exist
        if 'priority' not in [col['name'] for col in inspect(db.engine).get_columns('task')]:
            with db.engine.connect() as conn:
                conn.execute('ALTER TABLE task ADD COLUMN priority VARCHAR(10) DEFAULT "Medium"')
            print('✅ Task.priority column added.')
        else:
            print('Task.priority column already exists.')

def convert_mood_to_rating(mood):
    """Convert old mood string to numeric rating"""
    mood_ratings = {
        'Happy': 5,
        'Meh': 3,
        'Sad': 2,
        'Angry': 1,
        'Anxious': 2
    }
    return mood_ratings.get(mood, 3)

def determine_day_win(checkin):
    """Determine if the day was a win based on old data"""
    # Consider it a win if energy and focus are high, or mood is good
    if checkin.energy_level >= 4 and checkin.focus_level >= 4:
        return True
    if checkin.mood == 'Happy':
        return True
    if checkin.energy_level >= 3 and checkin.focus_level >= 3:
        return True
    return False

def determine_overall_rating(checkin):
    """Determine overall day rating based on old data"""
    if checkin.mood == 'Happy' and checkin.energy_level >= 4:
        return '😀'
    elif checkin.mood in ['Sad', 'Angry', 'Anxious'] or checkin.energy_level <= 2:
        return '😞'
    else:
        return '😐'

def create_sample_data():
    """Create sample data for testing"""
    with app.app_context():
        print("Creating sample data...")
        db.create_all()  # Ensure all tables exist
        
        # Create a test user
        user = User.query.filter_by(username='testuser').first()
        if not user:
            user = User(username='testuser', email='test@example.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            print("✅ Created test user: testuser / password123")
        
        # Create sample check-ins for the last 7 days
        for i in range(7):
            check_date = date.today() - timedelta(days=i)
            
            # Morning check-in
            morning = CheckIn(
                user_id=user.id,
                date=check_date,
                time_of_day='morning',
                sleep_hours=7.5 - (i * 0.5),
                sleep_quality=4 - (i % 2),
                energy_level=4 - (i % 3),
                morning_goal=f"Complete task {i+1}",
                anxiety_level="" if i % 2 == 0 else "Some stress about deadlines"
            )
            db.session.add(morning)
            
            # Evening check-in
            evening = CheckIn(
                user_id=user.id,
                date=check_date,
                time_of_day='evening',
                goal_accomplished=i % 2 == 0,
                mood_rating=4 - (i % 3),
                exercise_done=i % 2 == 0,
                what_drained_you="" if i % 2 == 0 else "Long meetings",
                gratitude=f"Grateful for day {i+1}",
                day_win=i % 2 == 0,
                overall_day_rating='😀' if i % 2 == 0 else '😐'
            )
            db.session.add(evening)
        
        db.session.commit()
        print("✅ Created sample data for the last 7 days")

if __name__ == '__main__':
    print("Daily Check-in App - Database Migration Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--sample':
        create_sample_data()
    else:
        migrate_database()
    
    print("\nMigration tool completed!") 