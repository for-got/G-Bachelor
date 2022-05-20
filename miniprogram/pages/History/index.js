import * as echarts from '../../ec-canvas/echarts';

const app = getApp();
var option=null;
function initChart(canvas, width, height, dpr) {
  const chart = echarts.init(canvas, null, {
    width: width,
    height: height,
    devicePixelRatio: dpr // new
  });
  canvas.setChart(chart);
  wx.request({
    url: `https://graduation.for-get.com/historyChart`,
    success: function (res) {
      option = res.data;
    }
  });
  chart.setOption(option);

  return chart;
}

Page({
  onShareAppMessage: function (res) {
    return {
      title: 'ECharts 可以在微信小程序中使用啦！',
      path: '/pages/index/index',
      success: function () { },
      fail: function () { }
    }
  },
  data: {
    ec: {
      onInit: initChart,
    }
  },

  onReady() {
    },
});
