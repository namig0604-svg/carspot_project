import Foundation

class APIService {
    static let shared = APIService()
    
    private let baseURL = "http://localhost:8000/api"
    private var authToken: String?
    
    private init() {}
    
    // MARK: - Authentication
    
    func login(email: String, password: String) async throws -> LoginResponse {
        let endpoint = "\(baseURL)/users/login"
        let request = LoginRequest(email: email, password: password)
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
        self.authToken = loginResponse.accessToken
        UserDefaults.standard.set(loginResponse.accessToken, forKey: "authToken")
        
        return loginResponse
    }
    
    func register(username: String, email: String, password: String, fullName: String?, country: String?, city: String?) async throws -> User {
        let endpoint = "\(baseURL)/users/register"
        let request = RegisterRequest(username: username, email: email, password: password, fullName: fullName, country: country, city: city)
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let user = try JSONDecoder().decode(User.self, from: data)
        return user
    }
    
    func logout() {
        self.authToken = nil
        UserDefaults.standard.removeObject(forKey: "authToken")
    }
    
    // MARK: - Events
    
    func getEvents(country: String? = nil, city: String? = nil, limit: Int = 50) async throws -> [Event] {
        var endpoint = "\(baseURL)/events/"
        var components = URLComponents(string: endpoint)
        var queryItems = [URLQueryItem]()
        
        if let country = country {
            queryItems.append(URLQueryItem(name: "country", value: country))
        }
        if let city = city {
            queryItems.append(URLQueryItem(name: "city", value: city))
        }
        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))
        
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }
        
        guard let url = components?.url else { throw APIError.invalidURL }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let events = try JSONDecoder().decode([Event].self, from: data)
        return events
    }
    
    func getNearbyEvents(latitude: Double, longitude: Double, radiusKm: Float = 50, country: String? = nil) async throws -> [EventMapData] {
        let endpoint = "\(baseURL)/events/map/nearby"
        var components = URLComponents(string: endpoint)
        var queryItems = [
            URLQueryItem(name: "latitude", value: String(latitude)),
            URLQueryItem(name: "longitude", value: String(longitude)),
            URLQueryItem(name: "radius_km", value: String(radiusKm))
        ]
        
        if let country = country {
            queryItems.append(URLQueryItem(name: "country", value: country))
        }
        
        components?.queryItems = queryItems
        
        guard let url = components?.url else { throw APIError.invalidURL }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let events = try JSONDecoder().decode([EventMapData].self, from: data)
        return events
    }
    
    func createEvent(title: String, description: String?, eventType: String, country: String, city: String?, locationName: String, latitude: Double, longitude: Double, address: String?, eventDate: Date, eventTime: String, durationMinutes: Int) async throws -> Event {
        let endpoint = "\(baseURL)/events/"
        
        let dateFormatter = ISO8601DateFormatter()
        let eventDateString = dateFormatter.string(from: eventDate)
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("Bearer \(authToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "title": title,
            "description": description ?? "",
            "event_type": eventType,
            "country": country,
            "city": city ?? "",
            "location_name": locationName,
            "latitude": latitude,
            "longitude": longitude,
            "address": address ?? "",
            "event_date": eventDateString,
            "event_time": eventTime,
            "duration_minutes": durationMinutes
        ]
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let event = try JSONDecoder().decode(Event.self, from: data)
        return event
    }
    
    func joinEvent(eventId: String) async throws -> [String: String] {
        let endpoint = "\(baseURL)/events/\(eventId)/join"
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(authToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let result = try JSONDecoder().decode([String: String].self, from: data)
        return result
    }
    
    // MARK: - Ratings
    
    func rateEvent(eventId: String, rating: Int, review: String?, atmosphereRating: Int? = nil, organizationRating: Int? = nil, locationRating: Int? = nil) async throws -> EventRating {
        let endpoint = "\(baseURL)/ratings/events"
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("Bearer \(authToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "event_id": eventId,
            "rating": rating,
            "review": review ?? "",
            "atmosphere_rating": atmosphereRating ?? NSNull(),
            "organization_rating": organizationRating ?? NSNull(),
            "location_rating": locationRating ?? NSNull()
        ]
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let eventRating = try JSONDecoder().decode(EventRating.self, from: data)
        return eventRating
    }
    
    func rateSpot(eventId: String, spotName: String, latitude: String, longitude: String, rating: Int, review: String?, accessibilityRating: Int? = nil, parkingRating: Int? = nil, safetyRating: Int? = nil) async throws -> SpotRating {
        let endpoint = "\(baseURL)/ratings/spots"
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("Bearer \(authToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "event_id": eventId,
            "spot_name": spotName,
            "latitude": latitude,
            "longitude": longitude,
            "rating": rating,
            "review": review ?? "",
            "accessibility_rating": accessibilityRating ?? NSNull(),
            "parking_rating": parkingRating ?? NSNull(),
            "safety_rating": safetyRating ?? NSNull()
        ]
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let spotRating = try JSONDecoder().decode(SpotRating.self, from: data)
        return spotRating
    }
    
    // MARK: - User Profile
    
    func getCurrentUserProfile() async throws -> UserProfile {
        let endpoint = "\(baseURL)/users/me"
        
        var urlRequest = URLRequest(url: URL(string: endpoint)!)
        urlRequest.httpMethod = "GET"
        urlRequest.setValue("Bearer \(authToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let userProfile = try JSONDecoder().decode(UserProfile.self, from: data)
        return userProfile
    }
}

// MARK: - Error Handling
enum APIError: Error {
    case invalidURL
    case invalidResponse
    case decodingError
    case networkError(Error)
}
