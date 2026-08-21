import XCTest

final class TodayBrowseTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testTodayBrowseDetailRoundTripPreservesBrowseScreen() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        let browse = app.buttons["today.browse"]
        XCTAssertTrue(browse.waitForExistence(timeout: 5))
        XCTAssertFalse(app.navigationBars.buttons["Search"].exists)
        XCTAssertFalse(app.navigationBars.buttons["Settings"].exists)
        browse.tap()

        let browseScreen = app.descendants(matching: .any)["screen.day.browse"]
        XCTAssertTrue(browseScreen.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["2 papers"].exists)
        attach(app.screenshot(), named: "Phase 17 Day Browse")
        let firstPaper = app.descendants(matching: .any)["browse.paper.2608.40002"]
        XCTAssertTrue(firstPaper.waitForExistence(timeout: 5))
        firstPaper.tap()

        let detailScreen = app.descendants(matching: .any)["screen.paper.detail"]
        XCTAssertTrue(detailScreen.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Action-Conditioned Video Dynamics"].exists)
        attach(app.screenshot(), named: "Phase 17 Paper Detail")
        app.navigationBars.buttons.element(boundBy: 0).tap()

        XCTAssertTrue(browseScreen.waitForExistence(timeout: 5))
        XCTAssertTrue(firstPaper.exists)
    }

    func testBrowseSaveUpdatesTodayProgressImmediately() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        let browse = app.buttons["today.browse"]
        XCTAssertTrue(browse.waitForExistence(timeout: 5))
        browse.tap()

        let save = app.buttons["paper.save.2608.40002"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        save.tap()
        XCTAssertTrue(app.buttons["paper.save.2608.40002"].staticTexts["Unsave"].waitForExistence(timeout: 5))

        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.staticTexts["1 reviewed"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["1 remaining"].exists)
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
