import SwiftUI

struct RootTabView: View {
    @Bindable var model: AppModel

    var body: some View {
        TabView {
            NavigationStack {
                TodayHomeView(model: model)
            }
            .tabItem { Label("Today", systemImage: "calendar") }
            .accessibilityIdentifier("tab.today")

            NavigationStack {
                TopicsHomeView(model: model)
            }
            .tabItem { Label("Topics", systemImage: "square.grid.2x2") }
            .accessibilityIdentifier("tab.topics")

            NavigationStack {
                SavedRootView()
            }
            .tabItem { Label("Saved", systemImage: "bookmark") }
            .accessibilityIdentifier("tab.saved")
        }
        .tint(PFTheme.primary)
        .accessibilityIdentifier("root.tabs")
    }
}

private struct SavedRootView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                Text("Saved")
                    .font(.largeTitle.bold())
                PFEmptyShell(
                    title: "No saved papers yet",
                    message: "Papers you save while reviewing will appear here."
                )
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.saved")
    }
}
