import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var userProfile: UserProfile?
    @State private var isLoading = false
    @State private var showSettings = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Background
                NFSTheme.darkBackground
                    .ignoresSafeArea()
                
                if isLoading {
                    ProgressView()
                        .tint(NFSTheme.neonBlue)
                } else if let profile = userProfile {
                    ScrollView {
                        VStack(spacing: 0) {
                            // Header Background
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    NFSTheme.neonBlue.opacity(0.2),
                                    NFSTheme.neonPurple.opacity(0.2)
                                ]),
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                            .frame(height: 150)
                            .overlay(
                                VStack(spacing: 12) {
                                    // Avatar
                                    if let avatarUrl = profile.avatarUrl {
                                        AsyncImage(url: URL(string: avatarUrl)) { image in
                                            image
                                                .resizable()
                                                .scaledToFill()
                                        } placeholder: {
                                            Circle()
                                                .fill(NFSTheme.darkCard)
                                                .overlay(
                                                    Image(systemName: "person.fill")
                                                        .foregroundColor(NFSTheme.neonBlue)
                                                )
                                        }
                                        .frame(width: 100, height: 100)
                                        .clipShape(Circle())
                                        .overlay(
                                            Circle()
                                                .stroke(NFSTheme.neonBlue, lineWidth: 3)
                                        )
                                    } else {
                                        Circle()
                                            .fill(NFSTheme.darkCard)
                                            .frame(width: 100, height: 100)
                                            .overlay(
                                                Image(systemName: "person.fill")
                                                    .font(.system(size: 40))
                                                    .foregroundColor(NFSTheme.neonBlue)
                                            )
                                            .overlay(
                                                Circle()
                                                    .stroke(NFSTheme.neonBlue, lineWidth: 3)
                                            )
                                    }
                                    
                                    VStack(spacing: 4) {
                                        Text(profile.fullName ?? profile.username)
                                            .font(.system(size: 20, weight: .bold))
                                            .foregroundColor(NFSTheme.textPrimary)
                                        
                                        Text("@\(profile.username)")
                                            .font(.system(size: 14))
                                            .foregroundColor(NFSTheme.textSecondary)
                                    }
                                },
                                alignment: .center
                            )
                            
                            // Stats
                            VStack(spacing: 16) {
                                HStack(spacing: 20) {
                                    StatCard(
                                        title: "Events Created",
                                        value: String(profile.eventsCreated),
                                        icon: "calendar.badge.plus",
                                        color: NFSTheme.neonRed
                                    )
                                    
                                    StatCard(
                                        title: "Events Joined",
                                        value: String(profile.eventsAttended),
                                        icon: "checkmark.circle.fill",
                                        color: NFSTheme.neonGreen
                                    )
                                    
                                    StatCard(
                                        title: "Rating",
                                        value: profile.averageRating,
                                        icon: "star.fill",
                                        color: NFSTheme.neonBlue
                                    )
                                }
                                .padding()
                                .background(NFSTheme.darkCard)
                                .cornerRadius(12)
                            }
                            .padding()
                            
                            // Bio Section
                            if let bio = profile.bio, !bio.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("About")
                                        .font(.system(size: 16, weight: .bold))
                                        .foregroundColor(NFSTheme.neonBlue)
                                    
                                    Text(bio)
                                        .font(.system(size: 14))
                                        .foregroundColor(NFSTheme.textSecondary)
                                        .lineSpacing(2)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding()
                                .background(NFSTheme.darkCard)
                                .cornerRadius(12)
                                .padding(.horizontal)
                            }
                            
                            // Location Section
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Location")
                                    .font(.system(size: 16, weight: .bold))
                                    .foregroundColor(NFSTheme.neonBlue)
                                
                                HStack(spacing: 12) {
                                    Image(systemName: "mappin.circle.fill")
                                        .font(.system(size: 20))
                                        .foregroundColor(NFSTheme.neonRed)
                                    
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(profile.country ?? "Unknown")
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundColor(NFSTheme.textPrimary)
                                        
                                        Text(profile.city ?? "Not specified")
                                            .font(.system(size: 12))
                                            .foregroundColor(NFSTheme.textSecondary)
                                    }
                                    
                                    Spacer()
                                }
                                .padding()
                                .background(NFSTheme.darkCard)
                                .cornerRadius(8)
                            }
                            .padding()
                            
                            // Membership Section
                            VStack(alignment: .leading, spacing: 12) {
                                if profile.isPremium {
                                    HStack(spacing: 12) {
                                        Image(systemName: "crown.fill")
                                            .font(.system(size: 20))
                                            .foregroundColor(NFSTheme.neonGreen)
                                        
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text("Premium Member")
                                                .font(.system(size: 14, weight: .bold))
                                                .foregroundColor(NFSTheme.neonGreen)
                                            
                                            Text("You have premium features unlocked")
                                                .font(.system(size: 12))
                                                .foregroundColor(NFSTheme.textSecondary)
                                        }
                                        
                                        Spacer()
                                    }
                                    .padding()
                                    .background(
                                        LinearGradient(
                                            gradient: Gradient(colors: [
                                                Color(UIColor(red: 0.0, green: 0.3, blue: 0.1, alpha: 1)),
                                                Color(UIColor(red: 0.0, green: 0.2, blue: 0.05, alpha: 1))
                                            ]),
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        )
                                    )
                                    .cornerRadius(8)
                                } else {
                                    VStack(alignment: .leading, spacing: 8) {
                                        HStack(spacing: 12) {
                                            Image(systemName: "star.fill")
                                                .foregroundColor(NFSTheme.neonBlue)
                                            Text("Upgrade to Premium")
                                                .font(.system(size: 14, weight: .bold))
                                        }
                                        
                                        Text("Get exclusive features and priority support")
                                            .font(.system(size: 12))
                                            .foregroundColor(NFSTheme.textSecondary)
                                        
                                        Button(action: {}) {
                                            Text("Upgrade Now")
                                                .font(.system(size: 12, weight: .bold))
                                                .frame(maxWidth: .infinity)
                                                .padding(.vertical, 8)
                                                .background(NFSTheme.neonBlue)
                                                .foregroundColor(.black)
                                                .cornerRadius(6)
                                        }
                                    }
                                    .padding()
                                    .background(NFSTheme.darkCard)
                                    .cornerRadius(8)
                                }
                            }
                            .padding()
                            
                            // Actions
                            VStack(spacing: 12) {
                                Button(action: { showSettings = true }) {
                                    HStack(spacing: 12) {
                                        Image(systemName: "gear")
                                            .font(.system(size: 16, weight: .semibold))
                                        Text("Settings")
                                            .font(.system(size: 14, weight: .semibold))
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12, weight: .semibold))
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding()
                                    .background(NFSTheme.darkCard)
                                    .foregroundColor(NFSTheme.neonBlue)
                                    .cornerRadius(8)
                                }
                                
                                Button(action: {
                                    authManager.logout()
                                }) {
                                    HStack(spacing: 12) {
                                        Image(systemName: "rectangle.portrait.and.arrow.right")
                                            .font(.system(size: 16, weight: .semibold))
                                        Text("Logout")
                                            .font(.system(size: 14, weight: .semibold))
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12, weight: .semibold))
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding()
                                    .background(NFSTheme.darkCard)
                                    .foregroundColor(NFSTheme.neonRed)
                                    .cornerRadius(8)
                                }
                            }
                            .padding()
                        }
                    }
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: { showSettings = true }) {
                        Image(systemName: "ellipsis.circle.fill")
                            .foregroundColor(NFSTheme.neonBlue)
                    }
                }
            }
            .onAppear {
                loadProfile()
            }
        }
    }
    
    private func loadProfile() {
        isLoading = true
        Task {
            do {
                let profile = try await APIService.shared.getCurrentUserProfile()
                DispatchQueue.main.async {
                    self.userProfile = profile
                    self.isLoading = false
                }
            } catch {
                print("Error loading profile: \(error)")
                self.isLoading = false
            }
        }
    }
}

// MARK: - Stat Card
struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(color)
            
            Text(value)
                .font(.system(size: 18, weight: .bold))
                .foregroundColor(NFSTheme.textPrimary)
            
            Text(title)
                .font(.system(size: 10))
                .foregroundColor(NFSTheme.textMuted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    ProfileView()
        .environmentObject(AuthManager())
}
