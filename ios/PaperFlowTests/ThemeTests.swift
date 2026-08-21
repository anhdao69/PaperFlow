import XCTest
@testable import PaperFlow

final class ThemeTests: XCTestCase {
    func testSpacingUsesEightPointDerivedScale() {
        XCTAssertEqual(PFTheme.Spacing.xSmall, 4)
        XCTAssertEqual(PFTheme.Spacing.small, 8)
        XCTAssertEqual(PFTheme.Spacing.medium, 12)
        XCTAssertEqual(PFTheme.Spacing.standard, 16)
        XCTAssertEqual(PFTheme.Spacing.large, 24)
        XCTAssertEqual(PFTheme.Spacing.xLarge, 32)
    }

    func testTapTargetAndRadiiMeetBaseline() {
        XCTAssertGreaterThanOrEqual(PFTheme.minimumTapTarget, 44)
        XCTAssertEqual(PFTheme.Radius.control, 10)
        XCTAssertEqual(PFTheme.Radius.tag, 8)
        XCTAssertEqual(PFTheme.Radius.card, 16)
        XCTAssertEqual(PFTheme.Radius.feature, 20)
    }
}
