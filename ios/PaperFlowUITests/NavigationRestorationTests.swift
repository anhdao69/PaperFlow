import XCTest

final class NavigationRestorationTests: XCTestCase {
    func testEachTabPreservesItsNavigationRoute() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        XCTAssertTrue(app.buttons["today.browse"].waitForExistence(timeout: 5))
        app.buttons["today.browse"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.day.browse"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Topics"].tap()
        let topic = app.descendants(matching: .any)["topic.row.world-models"]
        XCTAssertTrue(topic.waitForExistence(timeout: 5))
        topic.tap()
        XCTAssertTrue(app.staticTexts["All papers in this topic"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Today"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.day.browse"].waitForExistence(timeout: 5))
        app.tabBars.buttons["Topics"].tap()
        XCTAssertTrue(app.staticTexts["All papers in this topic"].waitForExistence(timeout: 5))
    }
}
