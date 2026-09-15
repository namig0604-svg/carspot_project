import SwiftUI

struct EventsListView: View {
    @EnvironmentObject var appState: AppState
    @State private var events: [Event] = []
    @State private var isLoading = false
    @State private var selectedEvent: Event?
    @State private var showCreateEvent = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Background
                NFSTheme.darkBackground
                    .ignoresSafeArea()
                
                VStack(spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Upcoming Events")
                                    .font(.system(size: 28, weight: .bold))
                                    .foregroundColor(NFSTheme.neonBlue)
                                
                                Text("in \(appState.selectedCountry)")
                                    .font(.system(size: 14))
                                    .foregroundColor(NFSTheme.textMuted)
                            }
                            
                            Spacer()
                            
                            Button(action: { showCreateEvent = true }) {
                                Image(systemName: "plus.circle.fill")
                                    .font(.system(size: 28))
                                    .foregroundColor(NFSTheme.neonGreen)
                            }
                        }
                        
                        // Filter buttons
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                FilterChip(title: "All", isSelected: true)
                                FilterChip(title: "Racing", isSelected: false)
                                FilterChip(title: "Photo", isSelected: false)
                                FilterChip(title: "Meetup", isSelected: false)
                            }
                        }
                    }
                    .padding()
                    .background(NFSTheme.darkCard)
                    
                    // Events List
                    if isLoading {
                        Spacer()
                        ProgressView()
                            .tint(NFSTheme.neonBlue)
                        Spacer()
                    } else if events.isEmpty {
                        Spacer()
                        VStack(spacing: 12) {
                            Image(systemName: "calendar.badge.exclamationmark")
                                .font(.system(size: 50))
                                .foregroundColor(NFSTheme.textMuted)
                            
                            Text("No events found")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(NFSTheme.textSecondary)
                            
                            Text("Create one or wait for others to post")
                                .font(.system(size: 14))
                                .foregroundColor(NFSTheme.textMuted)
                        }
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: 12) {
                                ForEach(events) { event in
                                    EventListItemView(event: event)
                                        .onTapGesture {
                                            selectedEvent = event
                                        }
                                }
                            }
                            .padding()
                        }
                    }
                }
            }
            .navigationDestination(isPresented: $showCreateEvent) {
                CreateEventView()
            }
            .onAppear {
                loadEvents()
            }
        }
    }
    
    private func loadEvents() {
        isLoading = true
        Task {
            do {
                let fetchedEvents = try await APIService.shared.getEvents(
                    country: appState.selectedCountry
                )
                DispatchQueue.main.async {
                    self.events = fetchedEvents
                    self.isLoading = false
                }
            } catch {
                print("Error loading events: \(error)")
                self.isLoading = false
            }
        }
    }
}

// MARK: - Event List Item
struct EventListItemView: View {
    let event: Event
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.title)
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(NFSTheme.textPrimary)
                        .lineLimit(2)
                    
                    HStack(spacing: 8) {
                        Label(event.eventType.replacingOccurrences(of: "_", with: " ").capitalized, systemImage: "car.fill")
                            .font(.system(size: 12))
                            .foregroundColor(eventTypeColor)
                        
                        Spacer()
                        
                        HStack(spacing: 4) {
                            Image(systemName: "star.fill")
                                .font(.system(size: 10))
                            Text(String(format: "%.1f", event.averageRating))
                                .font(.system(size: 12))
                        }
                        .foregroundColor(NFSTheme.neonGreen)
                    }
                }
                
                Spacer()
                
                // Status
                VStack(alignment: .center, spacing: 4) {
                    Text("\(event.participantsCount)")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(NFSTheme.neonBlue)
                    
                    Text("joined")
                        .font(.system(size: 10))
                        .foregroundColor(NFSTheme.textMuted)
                }
            }
            
            Divider()
                .background(Color(UIColor(red: 0.2, green: 0.2, blue: 0.3, alpha: 1)))
            
            // Details
            HStack(spacing: 16) {
                HStack(spacing: 8) {
                    Image(systemName: "calendar")
                        .font(.system(size: 12))
                        .foregroundColor(NFSTheme.neonBlue)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Date")
                            .font(.system(size: 10))
                            .foregroundColor(NFSTheme.textMuted)
                        Text(formatDate(event.eventDate))
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(NFSTheme.textPrimary)
                    }
                }
                
                Spacer()
                
                HStack(spacing: 8) {
                    Image(systemName: "clock.fill")
                        .font(.system(size: 12))
                        .foregroundColor(NFSTheme.neonRed)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Time")
                            .font(.system(size: 10))
                            .foregroundColor(NFSTheme.textMuted)
                        Text(event.eventTime)
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(NFSTheme.textPrimary)
                    }
                }
                
                Spacer()
                
                HStack(spacing: 8) {
                    Image(systemName: "location.fill")
                        .font(.system(size: 12))
                        .foregroundColor(NFSTheme.neonGreen)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Distance")
                            .font(.system(size: 10))
                            .foregroundColor(NFSTheme.textMuted)
                        Text(event.city ?? "Unknown")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(NFSTheme.textPrimary)
                            .lineLimit(1)
                    }
                }
            }
        }
        .padding()
        .background(NFSTheme.darkCard)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(
                    LinearGradient(
                        gradient: Gradient(colors: [eventTypeColor.opacity(0.3), eventTypeColor.opacity(0)]),
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
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
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: dateString) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateFormat = "MMM dd"
            return displayFormatter.string(from: date)
        }
        return dateString
    }
}

// MARK: - Filter Chip
struct FilterChip: View {
    let title: String
    let isSelected: Bool
    
    var body: some View {
        Text(title)
            .font(.system(size: 12, weight: .semibold))
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(isSelected ? NFSTheme.neonBlue : NFSTheme.darkBackground)
            .foregroundColor(isSelected ? .black : NFSTheme.textSecondary)
            .cornerRadius(6)
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(isSelected ? Color.clear : NFSTheme.neonBlue.opacity(0.3), lineWidth: 1)
            )
    }
}

// MARK: - Create Event View
struct CreateEventView: View {
    @Environment(\.dismiss) var dismiss
    @State private var title = ""
    @State private var description = ""
    @State private var eventType = "auto_meetup"
    @State private var locationName = ""
    @State private var eventDate = Date()
    @State private var eventTime = "20:00"
    @State private var durationMinutes = 120
    @State private var isLoading = false
    
    var body: some View {
        Form {
            Section(header: Text("Event Details").foregroundColor(NFSTheme.neonBlue)) {
                TextField("Event Title", text: $title)
                TextField("Location Name", text: $locationName)
                
                Picker("Event Type", selection: $eventType) {
                    Text("Auto Meetup").tag("auto_meetup")
                    Text("Racing").tag("racing")
                    Text("Photo Session").tag("photo_session")
                }
            }
            
            Section(header: Text("When?").foregroundColor(NFSTheme.neonBlue)) {
                DatePicker("Date", selection: $eventDate, displayedComponents: .date)
                TextField("Time (HH:mm)", text: $eventTime)
                Stepper("Duration: \(durationMinutes) min", value: $durationMinutes, step: 30, in: 30...480)
            }
            
            Section(header: Text("Description").foregroundColor(NFSTheme.neonBlue)) {
                TextEditor(text: $description)
                    .frame(height: 100)
            }
        }
        .navigationTitle("Create Event")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(action: {
                    Task {
                        isLoading = true
                        do {
                            _ = try await APIService.shared.createEvent(
                                title: title,
                                description: description.isEmpty ? nil : description,
                                eventType: eventType,
                                country: "Georgia",
                                city: nil,
                                locationName: locationName,
                                latitude: 41.7151,
                                longitude: 44.7671,
                                address: nil,
                                eventDate: eventDate,
                                eventTime: eventTime,
                                durationMinutes: durationMinutes
                            )
                            dismiss()
                        } catch {
                            print("Error creating event: \(error)")
                        }
                        isLoading = false
                    }
                }) {
                    Text(isLoading ? "Creating..." : "Done")
                        .foregroundColor(NFSTheme.neonGreen)
                }
                .disabled(isLoading || title.isEmpty || locationName.isEmpty)
            }
        }
    }
}

#Preview {
    EventsListView()
        .environmentObject(AppState())
}
