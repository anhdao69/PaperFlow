import XCTest

final class AccessibilityUITests: XCTestCase {
    func testLargestDynamicTypeKeepsPrimaryActionsReachable() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        let browse = app.buttons["today.browse"]
        let swipe = app.buttons["today.swipe"]
        XCTAssertTrue(browse.waitForExistence(timeout: 5))
        XCTAssertTrue(swipe.exists)
        XCTAssertTrue(app.tabBars.buttons["Today"].exists)
        XCTAssertTrue(app.tabBars.buttons["Topics"].exists)
        XCTAssertTrue(app.tabBars.buttons["Saved"].exists)
        scrollToHittable(browse, in: app)
        XCTAssertTrue(browse.isHittable)
        attach(app.screenshot(), named: "Phase 21 Accessibility XXXL Today")

        browse.tap()
        XCTAssertTrue(app.buttons["browse.filter"].waitForExistence(timeout: 5))
        let save = app.buttons["paper.save.2608.40002"]
        scrollToHittable(save, in: app)
        XCTAssertTrue(save.isHittable)
        app.navigationBars.buttons.element(boundBy: 0).tap()
        scrollToHittable(swipe, in: app)
        XCTAssertTrue(swipe.isHittable)
    }

    private func scrollToHittable(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0 ..< 8 where !element.isHittable { app.swipeUp() }
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
