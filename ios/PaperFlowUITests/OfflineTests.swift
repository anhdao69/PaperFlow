import XCTest

final class OfflineTests: XCTestCase {
    func testCachedOfflineContentAndPersonalActionsRemainAvailable() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--ui-testing-cached-offline"]
        app.launch()

        XCTAssertTrue(app.descendants(matching: .any)["state.offline"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any)["state.error.banner"].exists)
        XCTAssertTrue(app.buttons["today.browse"].exists)
        app.buttons["today.browse"].tap()
        let save = app.buttons["paper.save.2608.40002"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        save.tap()

        app.tabBars.buttons["Saved"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["state.offline"].waitForExistence(timeout: 5))
        app.buttons["saved.open.queue"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["saved.paper.2608.40002"].waitForExistence(timeout: 5))
        attach(app.screenshot(), named: "Phase 21 Cached Offline Saved")
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
