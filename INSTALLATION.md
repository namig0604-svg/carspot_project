# CarSpot - Installation Guide

## Backend Setup (Python/FastAPI)

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Docker & Docker Compose (optional)

### 2. Installation Steps

#### Option A: Using Docker Compose (Recommended)

```bash
cd carspot_project

# Start PostgreSQL and API server
docker-compose up --build

# API will be available at http://localhost:8000
# Docs: http://localhost:8000/docs
```

#### Option B: Manual Setup

```bash
cd carspot_project

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup PostgreSQL (in another terminal)
# Create database:
psql -U postgres
CREATE DATABASE carspot_db;
CREATE USER carspot_user WITH PASSWORD 'carspot_password';
GRANT ALL PRIVILEGES ON DATABASE carspot_db TO carspot_user;
\q

# Run migrations (creates tables)
python -c "from app.database import init_db; init_db()"

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Test the API

Open http://localhost:8000/docs for interactive API documentation

Test endpoints:
```bash
# Register user
curl -X POST "http://localhost:8000/api/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123",
    "country": "Georgia"
  }'

# Login
curl -X POST "http://localhost:8000/api/users/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'

# Get events
curl -X GET "http://localhost:8000/api/events?country=Georgia&limit=50"
```

---

## iOS App Setup

### 1. Prerequisites
- Xcode 15+
- iOS 17+
- Swift 5.9+

### 2. Setup Steps

1. **Open in Xcode**
   ```bash
   # Open the iOS project
   open CarSpot-iOS/CarSpot.xcodeproj
   ```

2. **Update API URL**
   - In `Views/ContentView.swift`, update `APIService` URL:
   ```swift
   private let baseURL = "http://YOUR_IP:8000/api"
   ```
   
   For local testing:
   - Get your machine IP: `ifconfig` (macOS) or `ipconfig` (Windows)
   - Use that IP instead of `localhost` since iPhone simulator needs to reach your Mac

3. **Configure Signing**
   - Select project in Xcode
   - Go to Signing & Capabilities
   - Select your team

4. **Build & Run**
   - Select simulator or device
   - Press Cmd+R to build and run

### 3. Testing the App

1. **Register Account**
   - Create new account
   - Select country (Georgia, Azerbaijan, etc.)
   - Confirm email

2. **View Map**
   - Tap "Map" tab
   - See nearby events
   - Switch countries with dropdown

3. **Create Event**
   - Tap "+" button on Events tab
   - Fill in details:
     - Title: "Friday Night Racing"
     - Location: "Tbilisi Center"
     - Date/Time
     - Event type (Racing, Photo, Meetup)
   - Submit

4. **Join Event**
   - Find event on map or in list
   - Tap "I'll Be There"
   - Your name appears in participants

5. **Rate Event**
   - Go to Profile
   - View past events
   - Leave rating and review

---

## API Endpoints Summary

### Authentication
- `POST /api/users/register` - Register new user
- `POST /api/users/login` - Login user
- `GET /api/users/me` - Get current user profile
- `PUT /api/users/me` - Update user profile

### Events
- `GET /api/events/` - Get events with filters
- `GET /api/events/{id}` - Get event details
- `POST /api/events/` - Create event
- `PUT /api/events/{id}` - Update event
- `GET /api/events/map/nearby` - Get nearby events (for map)
- `POST /api/events/{id}/join` - Join event
- `POST /api/events/{id}/leave` - Leave event

### Ratings
- `POST /api/ratings/events` - Rate event
- `GET /api/ratings/events/{event_id}` - Get event ratings
- `POST /api/ratings/spots` - Rate location/spot
- `GET /api/ratings/spots/{event_id}` - Get spot ratings
- `POST /api/ratings/users` - Rate user
- `GET /api/ratings/users/{user_id}` - Get user ratings

---

## Database Schema

### Tables
- `users` - User profiles and authentication
- `events` - Car meetup events
- `event_participants` - Who's attending which events
- `photos` - Event photos
- `photo_likes` - Likes on photos
- `photo_comments` - Comments on photos
- `event_ratings` - Ratings for events
- `user_ratings` - User ratings/reviews
- `spot_ratings` - Location ratings

---

## Features Implemented

✅ **MVP Features:**
- User registration & authentication (JWT)
- Create & manage events
- Interactive map with event markers
- Join/leave events
- Event ratings & reviews
- Spot/location ratings
- User profiles
- Dark theme (NFS Underground style)
- Multi-country support (Georgia, Azerbaijan, Armenia, Kazakhstan, Turkey, Russia)

🚀 **Features to Add:**
- Photo upload from events
- Real-time chat
- Push notifications
- Payment/subscription system
- Advanced search & filtering
- Event analytics
- Leaderboards

---

## Configuration Files

### .env
```
DATABASE_URL=postgresql://carspot_user:carspot_password@localhost:5432/carspot_db
SECRET_KEY=your-super-secret-key
DEBUG=True
```

### CORS Origins (for different platforms)
```
http://localhost
http://localhost:3000
http://192.168.1.100:8100  # iOS simulator
```

---

## Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Kill process on port 8000
lsof -i :8000
kill -9 <PID>
```

**Database connection error:**
- Ensure PostgreSQL is running
- Check DATABASE_URL in .env
- Verify database credentials

**Module not found:**
```bash
pip install -r requirements.txt --upgrade
```

### iOS Issues

**Cannot connect to API:**
- Use your machine IP instead of `localhost`
- Check firewall settings
- Verify API server is running

**Xcode build errors:**
- Clean build folder: Cmd+Shift+K
- Update Swift packages: File → Packages → Update to Latest Package Versions

**Simulator issues:**
- Reset simulator: Device → Erase All Content and Settings
- Restart Xcode

---

## Next Steps

1. Deploy backend to cloud (AWS, DigitalOcean, Railway, etc.)
2. Update iOS API URL to production
3. Add photo upload functionality
4. Integrate payment system (Stripe, Yandex.Kassa)
5. Add push notifications
6. Deploy to App Store

---

## Support

For issues or questions, create an issue on GitHub or contact the team.

Happy coding! 🚗💨
