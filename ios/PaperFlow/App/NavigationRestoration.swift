import Observation
import SwiftUI

enum PaperFlowTab: Hashable {
    case today
    case topics
    case saved
}

@MainActor
@Observable
final class NavigationRestoration {
    var selectedTab: PaperFlowTab = .today
    var todayPath = NavigationPath()
    var topicsPath = NavigationPath()
    var savedPath = NavigationPath()
}
