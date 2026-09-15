import SwiftUI

struct AuthenticationView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var isLoginMode = true
    
    var body: some View {
        ZStack {
            // Background with gradient
            LinearGradient(
                gradient: Gradient(colors: [
                    Color(UIColor(red: 0.05, green: 0.05, blue: 0.08, alpha: 1)),
                    Color(UIColor(red: 0.1, green: 0.08, blue: 0.15, alpha: 1))
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 20) {
                // Logo
                VStack(spacing: 10) {
                    Image(systemName: "car.fill")
                        .font(.system(size: 60))
                        .foregroundColor(NFSTheme.neonBlue)
                    
                    Text("CarSpot")
                        .font(.system(size: 50, weight: .black, design: .default))
                        .foregroundColor(NFSTheme.neonBlue)
                        .tracking(2)
                    
                    Text("Auto Meetup Finder for СНГ")
                        .font(.system(size: 14, weight: .semibold, design: .default))
                        .foregroundColor(NFSTheme.neonBlue2)
                }
                .padding(.bottom, 30)
                
                // Tab Toggle
                HStack(spacing: 0) {
                    Button(action: { isLoginMode = true }) {
                        Text("Login")
                            .font(.system(size: 16, weight: .semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(isLoginMode ? NFSTheme.neonBlue : Color.clear)
                            .foregroundColor(isLoginMode ? Color.black : NFSTheme.textSecondary)
                    }
                    .cornerRadius(8, corners: [.topLeft, .bottomLeft])
                    
                    Button(action: { isLoginMode = false }) {
                        Text("Register")
                            .font(.system(size: 16, weight: .semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(!isLoginMode ? NFSTheme.neonRed : Color.clear)
                            .foregroundColor(!isLoginMode ? Color.white : NFSTheme.textSecondary)
                    }
                    .cornerRadius(8, corners: [.topRight, .bottomRight])
                }
                .background(NFSTheme.darkCard)
                .cornerRadius(8)
                .padding(.horizontal)
                
                // Form
                if isLoginMode {
                    LoginFormView()
                } else {
                    RegisterFormView()
                }
                
                Spacer()
            }
            .padding()
        }
    }
}

// MARK: - Login Form
struct LoginFormView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var email = ""
    @State private var password = ""
    
    var body: some View {
        VStack(spacing: 16) {
            // Email
            VStack(alignment: .leading, spacing: 8) {
                Text("Email")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                TextField("your@email.com", text: $email)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
                    .foregroundColor(NFSTheme.textPrimary)
            }
            
            // Password
            VStack(alignment: .leading, spacing: 8) {
                Text("Password")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                SecureField("••••••••", text: $password)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
                    .foregroundColor(NFSTheme.textPrimary)
            }
            
            // Error message
            if let error = authManager.errorMessage {
                Text(error)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(NFSTheme.neonRed)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color(UIColor(red: 0.3, green: 0.05, blue: 0.1, alpha: 1)))
                    .cornerRadius(6)
            }
            
            // Login Button
            Button(action: {
                Task {
                    await authManager.login(email: email, password: password)
                }
            }) {
                if authManager.isLoading {
                    ProgressView()
                        .tint(Color.black)
                } else {
                    Text("LOGIN")
                        .font(.system(size: 16, weight: .bold))
                        .tracking(1)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                LinearGradient(
                    gradient: Gradient(colors: [NFSTheme.neonBlue, NFSTheme.neonBlue2]),
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .cornerRadius(8)
            .foregroundColor(Color.black)
            .disabled(authManager.isLoading)
        }
        .padding()
    }
}

// MARK: - Register Form
struct RegisterFormView: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var appState: AppState
    @State private var username = ""
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var fullName = ""
    @State private var selectedCountry = "Georgia"
    @State private var selectedCity = ""
    
    var body: some View {
        VStack(spacing: 16) {
            // Username
            VStack(alignment: .leading, spacing: 8) {
                Text("Username")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                TextField("username", text: $username)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
            }
            
            // Email
            VStack(alignment: .leading, spacing: 8) {
                Text("Email")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                TextField("your@email.com", text: $email)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
            }
            
            // Full Name
            VStack(alignment: .leading, spacing: 8) {
                Text("Full Name (Optional)")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                TextField("Your Name", text: $fullName)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
            }
            
            // Country
            VStack(alignment: .leading, spacing: 8) {
                Text("Country")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                Picker("Country", selection: $selectedCountry) {
                    ForEach(appState.supportedCountries, id: \.self) { country in
                        Text(country).tag(country)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(NFSTheme.darkCard)
                .cornerRadius(8)
            }
            
            // Password
            VStack(alignment: .leading, spacing: 8) {
                Text("Password")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(NFSTheme.textSecondary)
                
                SecureField("••••••••", text: $password)
                    .font(.system(size: 16))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(8)
            }
            
            // Error message
            if let error = authManager.errorMessage {
                Text(error)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(NFSTheme.neonRed)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color(UIColor(red: 0.3, green: 0.05, blue: 0.1, alpha: 1)))
                    .cornerRadius(6)
            }
            
            // Register Button
            Button(action: {
                Task {
                    await authManager.register(
                        username: username,
                        email: email,
                        password: password,
                        fullName: fullName.isEmpty ? nil : fullName,
                        country: selectedCountry,
                        city: selectedCity.isEmpty ? nil : selectedCity
                    )
                }
            }) {
                if authManager.isLoading {
                    ProgressView()
                        .tint(Color.white)
                } else {
                    Text("REGISTER")
                        .font(.system(size: 16, weight: .bold))
                        .tracking(1)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                LinearGradient(
                    gradient: Gradient(colors: [NFSTheme.neonRed, Color(UIColor(red: 1.0, green: 0.3, blue: 0.5, alpha: 1))]),
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .cornerRadius(8)
            .foregroundColor(Color.white)
            .disabled(authManager.isLoading)
        }
        .padding()
    }
}

// MARK: - Custom Corner Radius
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners
    
    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

#Preview {
    AuthenticationView()
        .environmentObject(AuthManager())
        .environmentObject(AppState())
}
