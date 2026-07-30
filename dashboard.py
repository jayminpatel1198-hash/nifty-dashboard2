        ):

            if (
                atm + i * STEP
            ) in strike_map:

                upper.append(
                    strike_map[
                        atm + i * STEP
                    ]
                )

            if (
                atm - i * STEP
            ) in strike_map:

                lower.append(
                    strike_map[
                        atm - i * STEP
                    ]
                )

        resistance = max(
            upper,
            key=lambda x:
            x["call"]["total_raw"]
        )

        support = max(
            lower,
            key=lambda x:
            x["put"]["total_raw"]
        )

        pairs = []

        for i in range(
            SIDE
        ):

            pairs.append({

                "upper":
                upper[i],

                "lower":
                lower[i]

            })

# PART 2B BELOW
        if atm not in strike_map:
            raise RuntimeError(
                "ATM strike data àª®àª³à«àª¯à«‹ àª¨àª¥à«€."
            )

        if not upper or not lower:
            raise RuntimeError(
                "ATM àª†àª¸àªªàª¾àª¸àª¨àª¾ strikes àª®àª³à«àª¯àª¾ àª¨àª¥à«€."
            )

        return jsonify({

            "nifty": round(
                nifty,
                2
            ),

            "atm": atm,

            "expiry": expiry,

            "time": datetime.now().strftime(
                "%H:%M:%S"
            ),

            "atm_data": strike_map[
                atm
            ],

            "pairs": pairs,

            "resistance": {

                "strike": resistance[
                    "strike"
                ],

                "oi": resistance[
                    "call"
                ][
                    "oi"
                ],

                "change": resistance[
                    "call"
                ][
                    "change"
                ],

                "total": resistance[
                    "call"
                ][
                    "total"
                ],

                "ltp": resistance[
                    "call"
                ][
                    "ltp"
                ],

                "iv": resistance[
                    "call"
                ][
                    "iv"
                ],

                "vwap": resistance[
                    "call"
                ][
                    "vwap"
                ],

                "status": resistance[
                    "call"
                ][
                    "status"
                ],

                "status_class": resistance[
                    "call"
                ][
                    "status_class"
                ]

            },

            "support": {

                "strike": support[
                    "strike"
                ],

                "oi": support[
                    "put"
                ][
                    "oi"
                ],

                "change": support[
                    "put"
                ][
                    "change"
                ],

                "total": support[
                    "put"
                ][
                    "total"
                ],

                "ltp": support[
                    "put"
                ][
                    "ltp"
                ],

                "iv": support[
                    "put"
                ][
                    "iv"
                ],

                "vwap": support[
                    "put"
                ][
                    "vwap"
                ],

                "status": support[
                    "put"
                ][
                    "status"
                ],

                "status_class": support[
                    "put"
                ][
                    "status_class"
                ]

            }

        })

    except Exception as error:

        return jsonify({

            "error": str(
                error
            )

        }), 500
                }
            );

        const data =
            await response.json();

        if(
            !response.ok ||
            data.error
        ){

            throw new Error(
                data.error ||
                "Load Failed"
            );

        }

        errorBox.style.display =
            "none";

        $("nifty").innerText =
            data.nifty;

        $("atm").innerText =
            data.atm;

        $("expiry").innerText =
            data.expiry;

        $("updated").innerText =
            data.time;

        $("atmTitle").innerText =
            "ATM " + data.atm;
                    $("atmSides").innerHTML =
            optionBox(
                data.atm_data.call,
                "CALL"
            )
            +
            optionBox(
                data.atm_data.put,
                "PUT"
            );

        $("pairs").innerHTML =
            data.pairs.map(
                pair => `
                    <div class="pair">

                        ${
                            strikeBox(
                                pair.upper,
                                "resstrike"
                            )
                        }

                        ${
                            strikeBox(
                                pair.lower,
                                "supstrike"
                            )
                        }

                    </div>
                `
            ).join("");

        const resistance =
            data.resistance;

        const support =
            data.support;

        $("resStrike").innerText =
            resistance.strike;

        $("resDetail").innerHTML =
            "Call OI "
            + resistance.oi

            + "<br>Change "
            + resistance.change

            + "<br>Price "
            + resistance.ltp

            + "<br>IV "
            + resistance.iv

            + "<br>VWAP "
            + resistance.vwap

            + "<br><b class='"
            + resistance.status_class
            + "'>"
            + resistance.status
            + "</b>"

            + "<br><b class='red'>"
            + "Total "
            + resistance.total
            + "</b>";

        $("supStrike").innerText =
            support.strike;

        $("supDetail").innerHTML =
            "Put OI "
            + support.oi

            + "<br>Change "
            + support.change

            + "<br>Price "
            + support.ltp

            + "<br>IV "
            + support.iv

            + "<br>VWAP "
            + support.vwap

            + "<br><b class='"
            + support.status_class
            + "'>"
            + support.status
            + "</b>"

            + "<br><b class='green'>"
            + "Total "
            + support.total
            + "</b>";

    }
    catch(error){

        errorBox.style.display =
            "block";

        errorBox.innerText =
            error.message;
    }
}


loadDashboard();


setInterval(
    loadDashboard,
    3000
);

</script>

</body>

</html>
"""


@app.route("/")
def home():

    return render_template_string(
        HTML
    )


@app.route("/health")
def health():

    return jsonify({

        "status": "ok",

        "token_configured":
            bool(TOKEN)

    })


if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=False

