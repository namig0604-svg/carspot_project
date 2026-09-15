import Foundation

// MARK: - User Models
struct User: Codable, Identifiable {
    let id: String
    let username: String
    let email: String
    let fullName: String?
    let avatarUrl: String?
    let bio: String?
    let country: String?
    let city: String?
    let isPremium: Bool
    let averageRating: String
    let eventsCreated: Int
    let eventsAttended: Int
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, username, email, bio, country, city
        case fullName = "full_name"
        case avatarUrl = "avatar_url"
        case isPremium = "is_premium"
        case averageRating = "average_rating"
        case eventsCreated = "events_created"
        case eventsAttended = "events_attended"
        case createdAt = "created_at"
    }
}

struct UserProfile: Codable {
    let id: String
    let username: String
    let email: String
    let fullName: String?
    let avatarUrl: String?
    let bio: String?
    let country: String?
    let city: String?
    let latitude: String?
    let longitude: String?
    let isPremium: Bool
    let isVerified: Bool
    let averageRating: String
    let eventsCreated: Int
    let eventsAttended: Int
    
    enum CodingKeys: String, CodingKey {
        case id, username, email, bio, country, city, latitude, longitude
        case fullName = "full_name"
        case avatarUrl = "avatar_url"
        case isPremium = "is_premium"
        case isVerified = "is_verified"
        case averageRating = "average_rating"
        case eventsCreated = "events_created"
        case eventsAttended = "events_attended"
    }
}

// MARK: - Event Models
struct Event: Codable, Identifiable {
    let id: String
    let creatorId: String
    let title: String
    let description: String?
    let eventType: String  // auto_meetup, racing, photo_session
    let country: String
    let city: String?
    let locationName: String
    let latitude: Double
    let longitude: Double
    let address: String?
    let eventDate: String
    let eventTime: String
    let durationMinutes: Int
    let participantsCount: Int
    let averageRating: Double
    let totalPhotos: Int
    let isActive: Bool
    let isCancelled: Bool
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, title, description, country, city, address, latitude, longitude
        case creatorId = "creator_id"
        case eventType = "event_type"
        case locationName = "location_name"
        case eventDate = "event_date"
        case eventTime = "event_time"
        case durationMinutes = "duration_minutes"
        case participantsCount = "participants_count"
        case averageRating = "average_rating"
        case totalPhotos = "total_photos"
        case isActive = "is_active"
        case isCancelled = "is_cancelled"
        case createdAt = "created_at"
    }
}

struct EventMapData: Codable, Identifiable {
    let id: String
    let title: String
    let eventType: String
    let locationName: String
    let latitude: Double
    let longitude: Double
    let eventTime: String
    let eventDate: String
    let participantsCount: Int
    let averageRating: Double
    let country: String
    let city: String?
    
    enum CodingKeys: String, CodingKey {
        case id, title, country, city, latitude, longitude
        case eventType = "event_type"
        case locationName = "location_name"
        case eventTime = "event_time"
        case eventDate = "event_date"
        case participantsCount = "participants_count"
        case averageRating = "average_rating"
    }
}

// MARK: - Rating Models
struct EventRating: Codable, Identifiable {
    let id: String
    let eventId: String
    let userId: String
    let rating: Int  // 1-5
    let review: String?
    let atmosphereRating: Int?
    let organizationRating: Int?
    let locationRating: Int?
    let isHelpful: Int
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, rating, review
        case eventId = "event_id"
        case userId = "user_id"
        case atmosphereRating = "atmosphere_rating"
        case organizationRating = "organization_rating"
        case locationRating = "location_rating"
        case isHelpful = "is_helpful"
        case createdAt = "created_at"
    }
}

struct SpotRating: Codable, Identifiable {
    let id: String
    let eventId: String
    let userId: String
    let spotName: String
    let latitude: String
    let longitude: String
    let rating: Int  // 1-5
    let review: String?
    let accessibilityRating: Int?
    let parkingRating: Int?
    let safetyRating: Int?
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, rating, review
        case eventId = "event_id"
        case userId = "user_id"
        case spotName = "spot_name"
        case latitude, longitude
        case accessibilityRating = "accessibility_rating"
        case parkingRating = "parking_rating"
        case safetyRating = "safety_rating"
        case createdAt = "created_at"
    }
}

// MARK: - Photo Model
struct Photo: Codable, Identifiable {
    let id: String
    let eventId: String
    let userId: String
    let photoUrl: String
    let thumbnailUrl: String?
    let caption: String?
    let description: String?
    let likesCount: Int
    let commentsCount: Int
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, caption, description
        case eventId = "event_id"
        case userId = "user_id"
        case photoUrl = "photo_url"
        case thumbnailUrl = "thumbnail_url"
        case likesCount = "likes_count"
        case commentsCount = "comments_count"
        case createdAt = "created_at"
    }
}

// MARK: - Authentication Models
struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct LoginResponse: Codable {
    let accessToken: String
    let tokenType: String
    let user: User
    
    enum CodingKeys: String, CodingKey {
        case tokenType = "token_type"
        case accessToken = "access_token"
        case user
    }
}

struct RegisterRequest: Codable {
    let username: String
    let email: String
    let password: String
    let fullName: String?
    let country: String?
    let city: String?
    
    enum CodingKeys: String, CodingKey {
        case username, email, password, country, city
        case fullName = "full_name"
    }
}
