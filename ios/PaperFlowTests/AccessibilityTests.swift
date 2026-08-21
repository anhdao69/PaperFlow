import SwiftUI
import XCTest
@testable import PaperFlow

@MainActor
final class AccessibilityTests: XCTestCase {
    func testLocalizedCountAndProgressLabelsAreUnambiguous() {
        XCTAssertEqual(PFAccessibility.paperCount(0), "0 papers")
        XCTAssertEqual(PFAccessibility.paperCount(1), "1 paper")
        XCTAssertEqual(PFAccessibility.paperCount(42), "42 papers")
        XCTAssertEqual(
            PFAccessibility.progress(reviewed: 18, total: 42),
            "18 of 42 papers reviewed"
        )
    }

    func testReducedMotionRemovesDecorativeSwipeRotationAndAnimation() {
        XCTAssertNil(PFMotionPolicy.animation(reduceMotion: true))
        XCTAssertEqual(PFMotionPolicy.rotation(7, reduceMotion: true), 0)
        XCTAssertEqual(PFMotionPolicy.rotation(7, reduceMotion: false), 7)
        XCTAssertNotNil(PFMotionPolicy.animation(reduceMotion: false))
    }

    func testHapticAbstractionEmitsOnlyExplicitSemanticEvents() {
        var events: [PFHapticEvent] = []
        let client = PFHapticClient { events.append($0) }

        client.trigger(.save)
        client.trigger(.completedReading)

        XCTAssertEqual(events, [.save, .completedReading])
    }

    func testPrimaryTargetMinimumIsAtLeastFortyFourPoints() {
        XCTAssertGreaterThanOrEqual(PFTheme.minimumTapTarget, 44)
    }

    func testIndependentNavigationPathsSurviveTabChanges() {
        let restoration = NavigationRestoration()
        restoration.todayPath.append("today-detail")
        restoration.topicsPath.append("topic-detail")
        restoration.selectedTab = .saved

        XCTAssertEqual(restoration.todayPath.count, 1)
        XCTAssertEqual(restoration.topicsPath.count, 1)
        XCTAssertEqual(restoration.savedPath.count, 0)
        XCTAssertEqual(restoration.selectedTab, .saved)
    }
}
