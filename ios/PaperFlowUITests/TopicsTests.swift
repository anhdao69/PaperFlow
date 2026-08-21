import XCTest

final class TopicsTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testDynamicTopicSubtopicHistoryUsesPublishedHierarchy() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()
        app.tabBars.buttons["Topics"].tap()

        XCTAssertTrue(app.staticTexts["Total Papers"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["2"].exists)
        XCTAssertTrue(app.staticTexts["papers in your research library"].exists)
        let worldModels = app.staticTexts["World Models"].firstMatch
        XCTAssertTrue(worldModels.exists)
        attach(app.screenshot(), named: "Phase 19 Topics")
        worldModels.tap()

        XCTAssertTrue(app.staticTexts["All papers in this topic"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Video World Models"].exists)
        attach(app.screenshot(), named: "Phase 19 Topic Detail")
        app.staticTexts["Video World Models"].tap()

        XCTAssertTrue(app.staticTexts["1 paper in full history"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Action-Conditioned Video Dynamics"].exists)
    }

    func testReviewedTodayPaperIsAbsentFromDefaultTopicSwipe() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()
        XCTAssertTrue(app.buttons["today.swipe"].waitForExistence(timeout: 5))
        app.buttons["today.swipe"].tap()
        let card = app.descendants(matching: .any)["swipe.card.2608.40002"]
        XCTAssertTrue(card.waitForExistence(timeout: 5))
        card.swipeLeft()

        app.tabBars.buttons["Topics"].tap()
        app.staticTexts["World Models"].firstMatch.tap()
        let topicSwipe = app.buttons["topic.swipe"]
        XCTAssertTrue(topicSwipe.waitForExistence(timeout: 5))
        topicSwipe.tap()

        XCTAssertTrue(app.descendants(matching: .any)["swipe.complete"].waitForExistence(timeout: 5))
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
