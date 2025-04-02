$("#signup").click(function () {
    $(".message").css("transform", "translateX(100%)");
    $(".message").removeClass("login").addClass("signup");
});

$("#login").click(function () {
    $(".message").css("transform", "translateX(0)");
    $(".message").removeClass("signup").addClass("login");
});