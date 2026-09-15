import SwiftUI

@main
struct CarSpotApp: App {
    @StateObject private var authManager = AuthManager()
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            if authManager.isLoggedIn {
                MainTabView()
                    .environmentObject(authManager)
                    .environmentObject(appState)
            } else {
                AuthenticationView()
                    .environmentObject(authManager)
            }
        }
    }
}

// MARK: - Main Tab View
struct MainTabView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var selectedTab = 0
    
    var body: some View {
        ZStack {
            // Background
            Color(UIColor(red: 0.05, green: 0.05, blue: 0.08, alpha: 1))
                .ignoresSafeArea()
            
            TabView(selection: $selectedTab) {
                // Map Tab
                MapView()
                    .tabItem {
                        Image(systemName: "map.fill")
                        Text("Map")
                    }
                    .tag(0)
                
                // Events Tab
                EventsListView()
                    .tabItem {
                        Image(systemName: "calendar")
                        Text("Events")
                    }
                    .tag(1)
                
                // Profile Tab
                ProfileView()
                    .tabItem {
                        Image(systemName: "person.fill")
                        Text("Profile")
                    }
                    .tag(2)
            }
            .preferredColorScheme(.dark)
        }
    }
}

// MARK: - Color Theme (NFS Underground Style)
struct NFSTheme {
    // Dark theme
    static let darkBackground = Color(UIColor(red: 0.05, green: 0.05, blue: 0.08, alpha: 1))
    static let darkCard = Color(UIColor(red: 0.1, green: 0.1, blue: 0.15, alpha: 1))
    
    // Neon colors
    static let neonBlue = Color(UIColor(red: 0.0, green: 0.6, blue: 1.0, alpha: 1))
    static let neonBlue2 = Color(UIColor(red: 0.2, green: 0.8, blue: 1.0, alpha: 1))
    static let neonRed = Color(UIColor(red: 1.0, green: 0.1, blue: 0.3, alpha: 1))
    static let neonGreen = Color(UIColor(red: 0.0, green: 1.0, blue: 0.4, alpha: 1))
    static let neonPurple = Color(UIColor(red: 0.8, green: 0.0, blue: 1.0, alpha: 1))
    
    // Text colors
    static let textPrimary = Color.white
    static let textSecondary = Color(UIColor(red: 0.7, green: 0.7, blue: 0.7, alpha: 1))
    static let textMuted = Color(UIColor(red: 0.5, green: 0.5, blue: 0.5, alpha: 1))
}

#Preview {
    ContentView()
}

struct ContentView: View {
    var body: some View {
        VStack {
            Text("CarSpot")
                .font(.system(size: 40, weight: .bold, design: .default))
                .foregroundColor(NFSTheme.neonBlue)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(NFSTheme.darkBackground)
    }
}
