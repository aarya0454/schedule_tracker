#!/usr/bin/env python3

from app import app, db, User, CheckIn
from datetime import date, datetime
import json

def test_database_migration():
    with app.app_context():
        # Create tables
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Test user creation
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        print("✅ User created successfully")
        
        # Test check-in with new fields
        checkin = CheckIn(
            user_id=user.id,
            sleep_hours=7.5,
            mood='Happy',
            energy_level=4,
            focus_level=4,
            tasks_done='Coding, reading, exercise',
            diet='Healthy meals',
            exercise='Gym workout',
            gratitude='Grateful for good health',
            habits=json.dumps(['reading', 'gym', 'coding'])
        )
        db.session.add(checkin)
        db.session.commit()
        print("✅ Check-in with new fields created successfully")
        
        # Test habit parsing
        habits = json.loads(checkin.habits)
        print(f"✅ Habits parsed: {habits}")
        
        # Test insights generation
        from app import generate_insights, analyze_keywords, analyze_habits
        insights = generate_insights([checkin])
        keywords = analyze_keywords([checkin])
        habits_analysis = analyze_habits([checkin])
        
        print(f"✅ Insights generated: {len(insights)} insights")
        print(f"✅ Keywords analyzed: {keywords}")
        print(f"✅ Habits analyzed: {habits_analysis}")
        
        print("\n🎉 All tests passed! Database migration successful.")

if __name__ == '__main__':
    test_database_migration() 