import SwiftUI

struct RootTabView: View {
    @Bindable var model: AppModel
    @State private var restoration = NavigationRestoration()

    var body: some View {
        @Bindable var restoration = restoration
        TabView(selection: $restoration.selectedTab) {
            NavigationStack(path: $restoration.todayPath) {
                TodayHomeView(model: model)
            }
            .tag(PaperFlowTab.today)
            .tabItem { Label("Today", systemImage: "calendar") }
            .accessibilityIdentifier("tab.today")

            NavigationStack(path: $restoration.topicsPath) {
                TopicsHomeView(model: model)
            }
            .tag(PaperFlowTab.topics)
            .tabItem { Label("Topics", systemImage: "square.grid.2x2") }
            .accessibilityIdentifier("tab.topics")

            NavigationStack(path: $restoration.savedPath) {
                SavedHomeView(model: model) { restoration.selectedTab = .today }
            }
            .tag(PaperFlowTab.saved)
            .tabItem { Label("Saved", systemImage: "bookmark") }
            .accessibilityIdentifier("tab.saved")
        }
        .tint(PFTheme.primary)
        .accessibilityIdentifier("root.tabs")
    }
}
