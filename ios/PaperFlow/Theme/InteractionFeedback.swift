import SwiftUI
import UIKit

enum PFHapticEvent: Equatable {
    case save
    case skip
    case completedReading
}

struct PFHapticClient {
    var trigger: @MainActor (PFHapticEvent) -> Void

    static let live = PFHapticClient { event in
        switch event {
        case .save, .completedReading:
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        case .skip:
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
    }
}

private struct PFHapticClientKey: EnvironmentKey {
    static let defaultValue = PFHapticClient.live
}

extension EnvironmentValues {
    var pfHaptics: PFHapticClient {
        get { self[PFHapticClientKey.self] }
        set { self[PFHapticClientKey.self] = newValue }
    }
}

enum PFMotionPolicy {
    static func animation(reduceMotion: Bool) -> Animation? {
        reduceMotion ? nil : .spring(response: 0.28, dampingFraction: 0.82)
    }

    static func rotation(_ proposedDegrees: Double, reduceMotion: Bool) -> Double {
        reduceMotion ? 0 : proposedDegrees
    }
}
