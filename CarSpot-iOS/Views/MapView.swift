import SwiftUI
import MapKit
import CoreLocation

struct MapView: View {
    @EnvironmentObject var appState: AppState
    @State private var events: [EventMapData] = []
    @State private var isLoading = false
    @State private var selectedEvent: EventMapData?
    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 41.7151, longitude: 44.7671),
        span: MKCoordinateSpan(latitudeDelta: 0.5, longitudeDelta: 0.5)
    )
    
    // Coordinates for countries
    let countryCoordinates: [String: CLLocationCoordinate2D] = [
        "Georgia": CLLocationCoordinate2D(latitude: 41.7151, longitude: 44.7671),
        "Azerbaijan": CLLocationCoordinate2D(latitude: 40.1792, longitude: 47.5769),
        "Armenia": CLLocationCoordinate2D(latitude: 40.0691, longitude: 45.0382),
        "Kazakhstan": CLLocationCoordinate2D(latitude: 48.0196, longitude: 66.9237),
        "Turkey": CLLocationCoordinate2D(latitude: 38.9637, longitude: 35.2433),
        "Russia": CLLocationCoordinate2D(latitude: 61.5240, longitude: 105.3188)
    ]
    
    var body: some View {
        ZStack {
            // Map
            Map(position: .constant(.region(region))) {
                ForEach(events) { event in
                    Annotation(event.title, coordinate: CLLocationCoordinate2D(latitude: event.latitude, longitude: event.longitude)) {
                        EventMapMarker(event: event, isSelected: selectedEvent?.id == event.id)
                            .onTapGesture {
                                selectedEvent = event
                            }
                    }
                }
            }
            .mapStyle(.dark)
            .ignoresSafeArea()
            
            // Top controls
            VStack {
                HStack(spacing: 12) {
                    // Country selector
                    Menu {
                        ForEach(appState.supportedCountries, id: \.self) { country in
                            Button(action: {
                                appState.selectedCountry = country
                                updateMapRegion()
                                loadEvents()
                            }) {
                                Label(country, systemImage: "mappin.circle.fill")
                            }
                        }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "mappin.circle.fill")
                            Text(appState.selectedCountry)
                                .font(.system(size: 14, weight: .semibold))
                            Image(systemName: "chevron.down")
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(NFSTheme.darkCard)
                        .foregroundColor(NFSTheme.neonBlue)
                        .cornerRadius(8)
                    }
                    
                    // Refresh button
                    Button(action: { loadEvents() }) {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 16, weight: .semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 10)
                            .background(NFSTheme.darkCard)
                            .foregroundColor(NFSTheme.neonGreen)
                            .cornerRadius(8)
                    }
                    
                    Spacer()
                }
                .padding()
                
                Spacer()
            }
            
            // Event details sheet
            if let selectedEvent = selectedEvent {
                VStack {
                    Spacer()
                    
                    EventDetailsCard(event: selectedEvent)
                        .transition(.move(edge: .bottom))
                }
                .ignoresSafeArea(edges: .bottom)
            }
        }
        .onAppear {
            loadEvents()
        }
    }
    
    private func updateMapRegion() {
        if let coordinate = countryCoordinates[appState.selectedCountry] {
            region = MKCoordinateRegion(
                center: coordinate,
                span: MKCoordinateSpan(latitudeDelta: 5.0, longitudeDelta: 5.0)
            )
        }
    }
    
    private func loadEvents() {
        isLoading = true
        Task {
            do {
                let nearbyEvents = try await APIService.shared.getNearbyEvents(
                    latitude: region.center.latitude,
                    longitude: region.center.longitude,
                    radiusKm: 100,
                    country: appState.selectedCountry
                )
                DispatchQueue.main.async {
                    self.events = nearbyEvents
                    self.isLoading = false
                }
            } catch {
                print("Error loading events: \(error)")
                self.isLoading = false
            }
        }
    }
}

// MARK: - Event Map Marker
struct EventMapMarker: View {
    let event: EventMapData
    let isSelected: Bool
    
    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: "mappin.circle.fill")
                .font(.system(size: isSelected ? 32 : 24))
                .foregroundColor(eventTypeColor)
            
            if isSelected {
                Text(event.title)
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(NFSTheme.darkCard)
                    .cornerRadius(4)
            }
        }
    }
    
    var eventTypeColor: Color {
        switch event.eventType {
        case "racing":
            return NFSTheme.neonRed
        case "photo_session":
            return NFSTheme.neonGreen
        case "auto_meetup":
            return NFSTheme.neonBlue
        default:
            return NFSTheme.neonPurple
        }
    }
}

// MARK: - Event Details Card
struct EventDetailsCard: View {
    @State private var showFullDetails = false
    let event: EventMapData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.title)
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(NFSTheme.textPrimary)
                    
                    HStack(spacing: 12) {
                        Label(event.eventType.replacingOccurrences(of: "_", with: " ").capitalized, systemImage: "car.fill")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(NFSTheme.neonBlue)
                        
                        Label("\(event.participantsCount) joined", systemImage: "person.2.fill")
                            .font(.system(size: 12))
                            .foregroundColor(NFSTheme.textSecondary)
                    }
                }
                
                Spacer()
                
                // Rating
                VStack(alignment: .center) {
                    Image(systemName: "star.fill")
                        .font(.system(size: 12))
                        .foregroundColor(NFSTheme.neonGreen)
                    
                    Text(String(format: "%.1f", event.averageRating))
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(NFSTheme.textPrimary)
                }
            }
            .padding()
            .background(NFSTheme.darkCard)
            
            Divider()
                .background(Color(UIColor(red: 0.2, green: 0.2, blue: 0.3, alpha: 1)))
            
            // Details
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    Image(systemName: "calendar")
                        .font(.system(size: 14))
                        .foregroundColor(NFSTheme.neonBlue)
                        .frame(width: 20)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Date & Time")
                            .font(.system(size: 12))
                            .foregroundColor(NFSTheme.textMuted)
                        Text("\(event.eventDate) at \(event.eventTime)")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(NFSTheme.textPrimary)
                    }
                }
                
                HStack(spacing: 12) {
                    Image(systemName: "location.fill")
                        .font(.system(size: 14))
                        .foregroundColor(NFSTheme.neonRed)
                        .frame(width: 20)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Location")
                            .font(.system(size: 12))
                            .foregroundColor(NFSTheme.textMuted)
                        Text(event.locationName)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(NFSTheme.textPrimary)
                    }
                }
            }
            .padding()
            .background(NFSTheme.darkCard)
            
            // Actions
            HStack(spacing: 12) {
                Button(action: {}) {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                        Text("I'll Be There")
                    }
                    .font(.system(size: 14, weight: .semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [NFSTheme.neonBlue, NFSTheme.neonBlue2]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .foregroundColor(.black)
                    .cornerRadius(8)
                }
                
                Button(action: { showFullDetails = true }) {
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 14, weight: .semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(NFSTheme.darkCard)
                        .foregroundColor(NFSTheme.neonGreen)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(NFSTheme.neonGreen, lineWidth: 1)
                        )
                }
            }
            .padding()
        }
        .background(NFSTheme.darkBackground)
        .cornerRadius(16, corners: [.topLeft, .topRight])
    }
}

#Preview {
    MapView()
        .environmentObject(AppState())
}
