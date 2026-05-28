import { useState } from 'react'
import './App.css'

function App() {
  const [activeMenu, setActiveMenu] = useState(false)

  const navigationLinks = [
    { name: 'Dashboard', href: '/dashboard', icon: '📊' },
    { name: 'Comparison', href: '/comparison', icon: '⚖️' },
    { name: 'Chatbot', href: '/chatbot', icon: '💬' },
    { name: 'Sources', href: '/sources', icon: '📰' },
    { name: 'Analysis', href: '/analysis', icon: '📈' },
  ]

  return (
    <div className="app-container">
      {/* Navigation Header */}
      <nav className="navbar">
        <div className="nav-content">
          <div className="logo-section">
            <span className="logo-icon">🎯</span>
            <h1 className="logo-text">SocialListen</h1>
          </div>
          <button 
            className={`menu-toggle ${activeMenu ? 'active' : ''}`}
            onClick={() => setActiveMenu(!activeMenu)}
            aria-label="Toggle menu"
          >
            ☰
          </button>
          <ul className={`nav-links ${activeMenu ? 'active' : ''}`}>
            {navigationLinks.map((link) => (
              <li key={link.name}>
                <a href={link.href} className="nav-link">
                  <span className="link-icon">{link.icon}</span>
                  {link.name}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <h2 className="hero-title">
            Real-Time Social Intelligence
          </h2>
          <p className="hero-subtitle">
            Monitor conversations, analyze sentiment, and gain actionable insights 
            across all social platforms
          </p>
          <div className="hero-buttons">
            <a href="/dashboard" className="btn btn-primary">
              Get Started
            </a>
            <button className="btn btn-secondary">
              Watch Demo
            </button>
          </div>
        </div>
        <div className="hero-visual">
          <div className="floating-card card-1">
            <span className="card-label">Sentiment Analysis</span>
            <div className="card-stat">92%</div>
          </div>
          <div className="floating-card card-2">
            <span className="card-label">Real-time Data</span>
            <div className="card-pulse">●</div>
          </div>
          <div className="floating-card card-3">
            <span className="card-label">Brands Tracked</span>
            <div className="card-stat">1.2K+</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <h2 className="section-title">Powerful Features</h2>
        <div className="features-grid">
          {navigationLinks.map((feature) => (
            <div key={feature.name} className="feature-card">
              <div className="feature-icon">{feature.icon}</div>
              <h3>{feature.name}</h3>
              <p>
                {feature.name === 'Dashboard' && 'Real-time monitoring and overview of all your brand mentions'}
              </p>
              <p>
                {feature.name === 'Comparison' && 'Compare sentiment and engagement across competitors'}
              </p>
              <p>
                {feature.name === 'Chatbot' && 'AI-powered assistant for quick insights and queries'}
              </p>
              <p>
                {feature.name === 'Sources' && 'Track mentions across all social media platforms'}
              </p>
              <p>
                {feature.name === 'Analysis' && 'In-depth analytics and trend detection'}
              </p>
              <a href={feature.href} className="feature-link">
                Explore →
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Stats Section */}
      <section className="stats-section">
        <div className="stat-item">
          <div className="stat-number">500M+</div>
          <div className="stat-label">Daily Posts Monitored</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">99.9%</div>
          <div className="stat-label">Uptime Guaranteed</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">&lt;100ms</div>
          <div className="stat-label">Real-time Latency</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">5K+</div>
          <div className="stat-label">Active Users</div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <h2>Ready to understand your audience?</h2>
        <p>Start monitoring social conversations in real-time</p>
        <a href="/dashboard" className="btn btn-primary btn-large">
          Start Free Trial
        </a>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>Platform</h4>
            <ul>
              {navigationLinks.map((link) => (
                <li key={link.name}>
                  <a href={link.href}>{link.name}</a>
                </li>
              ))}
            </ul>
          </div>
          <div className="footer-section">
            <h4>Company</h4>
            <ul>
              <li><a href="/">About</a></li>
              <li><a href="/">Blog</a></li>
              <li><a href="/">Careers</a></li>
              <li><a href="/">Contact</a></li>
            </ul>
          </div>
          <div className="footer-section">
            <h4>Legal</h4>
            <ul>
              <li><a href="/">Privacy</a></li>
              <li><a href="/">Terms</a></li>
              <li><a href="/">Security</a></li>
              <li><a href="/">Compliance</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; 2026 SocialListen. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

export default App
