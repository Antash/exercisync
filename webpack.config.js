var path = require("path")
var webpack = require('webpack')
var BundleTracker = require('webpack-bundle-tracker')

module.exports = {
  context: __dirname,

  entry: {
    exercisyncApp: './tapiriik/frontend/app',
  },

  output: {
    path: path.resolve('./tapiriik/web/static/js/bundles/'),
    filename: "[name].js"
  },

  plugins: [
    new BundleTracker({ filename: './webpack-stats.json' }),
    new webpack.HotModuleReplacementPlugin()
  ],

  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: ['babel-loader']
      },
      {
        test: /\.css$/, 
        loader: 'style-loader!css-loader'
      },
    ],
  },

  resolve: {
    modules: ['node_modules'],
    extensions: ['.js', '.jsx']
  }
}