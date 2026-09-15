import SwiftUI
import Combine

class AuthManager: ObservableObject {
    @Published var isLoggedIn = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    init() {
        checkAuthStatus()
    }
    
    func checkAuthStatus() {
        if let token = UserDefaults.standard.string(forKey: "authToken") {
            self.isLoggedIn = true
            // Could load user profile here
        } else {
            self.isLoggedIn = false
        }
    }
    
    func login(email: String, password: String) async {
        DispatchQueue.main.async {
            self.isLoading = true
            self.errorMessage = nil
        }
        
        do {
            let loginResponse = try await APIService.shared.login(email: email, password: password)
            
            DispatchQueue.main.async {
                self.currentUser = loginResponse.user
                self.isLoggedIn = true
                self.isLoading = false
            }
        } catch {
            DispatchQueue.main.async {
                self.errorMessage = "Login failed: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    func register(username: String, email: String, password: String, fullName: String?, country: String?, city: String?) async {
        DispatchQueue.main.async {
            self.isLoading = true
            self.errorMessage = nil
        }
        
        do {
            let user = try await APIService.shared.register(
                username: username,
                email: email,
                password: password,
                fullName: fullName,
                country: country,
                city: city
            )
            
            DispatchQueue.main.async {
                self.currentUser = user
                self.errorMessage = "Registration successful! Please login."
                self.isLoading = false
            }
        } catch {
            DispatchQueue.main.async {
                self.errorMessage = "Registration failed: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    func logout() {
        APIService.shared.logout()
        self.currentUser = nil
        self.isLoggedIn = false
    }
}

class AppState: ObservableObject {
    @Published var selectedCountry: String = "Georgia"
    @Published var selectedCity: String?
    @Published var userLocation: (latitude: Double, longitude: Double)?
    @Published var isDarkMode: Bool = true
    
    let supportedCountries = ["Georgia", "Azerbaijan", "Armenia", "Kazakhstan", "Turkey", "Russia"]
}
