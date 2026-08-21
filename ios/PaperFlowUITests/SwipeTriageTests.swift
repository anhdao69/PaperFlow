import XCTest

final class SwipeTriageTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testDetailRoundTripGestureButtonsUndoResumeAndCompletion() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        let swipe = app.buttons["today.swipe"]
        XCTAssertTrue(swipe.waitForExistence(timeout: 5))
        swipe.tap()

        let first = app.descendants(matching: .any)["swipe.card.2608.40002"]
        XCTAssertTrue(first.waitForExistence(timeout: 5))
        attach(app.screenshot(), named: "Phase 18 Swipe")
        first.tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.paper.detail"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(first.waitForExistence(timeout: 5))

        app.buttons["swipe.save"].tap()
        let second = app.descendants(matching: .any)["swipe.card.2608.40001"]
        XCTAssertTrue(second.waitForExistence(timeout: 5))
        app.buttons["swipe.undo"].tap()
        XCTAssertTrue(first.waitForExistence(timeout: 5))

        first.swipeLeft()
        XCTAssertTrue(second.waitForExistence(timeout: 5))
        app.buttons["swipe.skip"].tap()

        let complete = app.descendants(matching: .any)["swipe.complete"]
        XCTAssertTrue(complete.waitForExistence(timeout: 5))
        attach(app.screenshot(), named: "Phase 18 Complete")
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
