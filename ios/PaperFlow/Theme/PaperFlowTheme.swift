import SwiftUI

enum PFTheme {
    static let primary = Color(red: 0.396, green: 0.329, blue: 0.965)
    static let primaryStrong = Color(red: 0.353, green: 0.271, blue: 0.961)
    static let primarySoft = Color(red: 0.945, green: 0.937, blue: 1)
    static let success = Color(red: 0.145, green: 0.647, blue: 0.416)
    static let successSoft = Color(red: 0.929, green: 0.976, blue: 0.953)
    static let danger = Color(red: 0.906, green: 0.31, blue: 0.345)
    static let dangerSoft = Color(red: 1, green: 0.945, blue: 0.949)
    static let warning = Color.orange
    static let background = Color(uiColor: .systemGroupedBackground)
    static let surface = Color(uiColor: .secondarySystemGroupedBackground)
    static let surfaceSecondary = Color(uiColor: .tertiarySystemGroupedBackground)
    static let textPrimary = Color.primary
    static let textSecondary = Color.secondary
    static let textTertiary = Color(uiColor: .tertiaryLabel)
    static let divider = Color(uiColor: .separator)

    enum Spacing {
        static let xSmall: CGFloat = 4
        static let small: CGFloat = 8
        static let medium: CGFloat = 12
        static let standard: CGFloat = 16
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
    }

    enum Radius {
        static let control: CGFloat = 10
        static let tag: CGFloat = 8
        static let card: CGFloat = 16
        static let feature: CGFloat = 20
    }

    static let minimumTapTarget: CGFloat = 44
}
