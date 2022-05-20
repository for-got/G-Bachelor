import * as echarts from '../../ec-canvas/echarts';

const app = getApp();
var timer = null;
var chart_control = null;
var old_temperature = [];
var old_humidity = [];
var idx = 0;
var run_flag = false;
Page({
    data: {
        ec: {
            // 将 lazyLoad 设为 true 后，需要手动初始化图表
            lazyLoad: false
        },
        isLoaded: false,
        isDisposed: false,
        data_load: "",
        lineChart: null,
    },
    onShareAppMessage: res => {
        return {
            title: 'ECharts 可以在微信小程序中使用啦！',
            path: '/pages/index/index',
            success: function () {
            },
            fail: function () {
            }
        }
    },

    onLoad(query) {
        wx.request({
            url: `https://graduation.for-get.com/lineChart`,
            success: (res) => {
                this.setData({
                    lineChart: res.data
                })
            }
        });
    },

    onReady: function () {
        // 获取组件
        this.ecComponent = this.selectComponent('#mychart-dom-bar');
    },

    // 点击按钮后初始化图表
    init: function () {
        this.ecComponent.init((canvas, width, height, dpr) => {
            // 获取组件的 canvas、width、height 后的回调函数
            // 在这里初始化图表
            const chart = echarts.init(canvas, null, {
                width: width,
                height: height,
                devicePixelRatio: dpr // new
            });
            chart.setOption(this.data.lineChart);

            // 将图表实例绑定到 this 上，可以在其他成员函数（如 dispose）中访问
            this.chart = chart;

            this.setData({
                isLoaded: true,
                isDisposed: false
            });
            chart_control = this.chart;
            setTimer();
            run_flag = true;
            // 注意这里一定要返回 chart 实例，否则会影响事件处理等
            return chart;
        });
    },

    dispose: function () {
        //if (this.chart) {
        //    this.chart.dispose();
        //}
        if(run_flag){
            clearInterval(timer);
            run_flag = false;
            this.setData({
                data_load: "继续加载数据",
            });
        }
        else{
            this.setData({
                data_load: "暂停数据加载",
            });
            run_flag = true;
            setTimer();
        }


        //this.setData({
        //    isDisposed: true
        //});
    },
    onHide: function () {
        clearTimeout(timer); // 清除定时器
    },

});
function setTimer() {
    timer = setTimeout(function () {
            wx.request({
                url: `https://graduation.for-get.com/lineDynamicData`,
                dataType: 'json',
                success: function (res){
                    old_temperature.push([idx, res.data.temperature]);
                    old_humidity.push([idx, res.data.humidity]);
                    chart_control.setOption({
                        series: [{
                            data: old_temperature
                        }, {
                            data: old_humidity
                        }]
                    });
                    idx++;
                }
            });
        setTimer();
    }, 666);
}